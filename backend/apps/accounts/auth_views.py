import secrets
from functools import lru_cache

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit import services as audit

from .models import User
from .serializers import LoginSerializer, MeSerializer

REFRESH_COOKIE = "fg_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth/"


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return make_password("not-a-real-password", hasher="bcrypt_sha256")


def _burn_hash(password: str) -> None:
    """Spend comparable time for unknown/inactive accounts so timing does not reveal which emails exist."""
    check_password(password, _dummy_hash())


class AccountLocked(exceptions.APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "account_locked"
    default_detail = "Too many failed attempts. Try again later."


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),  # type: ignore[attr-defined]
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Strict",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, samesite="Strict")


class PublicAuthView(APIView):
    """Unauthenticated endpoint that still reports failures as 401 (not 403) via a Bearer challenge."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get_authenticate_header(self, request):  # noqa: ANN001, ANN201
        return "Bearer"


class LoginView(PublicAuthView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):  # noqa: ANN001, ANN201
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].strip().lower()
        password = ser.validated_data["password"]

        user = User.objects.select_related("role").filter(email__iexact=email).first()
        if user is not None and user.is_locked:
            audit.log(
                "auth.login_blocked_locked",
                request=request,
                actor=user,
                resource_type="user",
                resource_id=user.pk,
            )
            raise AccountLocked()

        if user is None or not user.is_active:
            _burn_hash(password)
            audit.log("auth.login_failed", request=request, actor=user, actor_email=email[:254])
            raise exceptions.AuthenticationFailed("Invalid email or password.", code="invalid_credentials")

        if not user.check_password(password):
            locked = user.register_failed_login()
            audit.log(
                "auth.login_locked_out" if locked else "auth.login_failed",
                request=request, actor=user, resource_type="user", resource_id=user.pk,
            )  # fmt: skip
            if locked:
                raise AccountLocked()
            raise exceptions.AuthenticationFailed("Invalid email or password.", code="invalid_credentials")

        user.register_successful_login()
        refresh = RefreshToken.for_user(user)
        audit.log("auth.login", request=request, actor=user, resource_type="user", resource_id=user.pk)
        response = Response({"access": str(refresh.access_token), "user": MeSerializer(user).data})
        _set_refresh_cookie(response, str(refresh))
        return response


class RefreshView(PublicAuthView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "refresh"

    def post(self, request):  # noqa: ANN001, ANN201
        raw = request.COOKIES.get(REFRESH_COOKIE)
        if not raw:
            raise exceptions.AuthenticationFailed("No refresh token.", code="no_refresh_token")
        ser = TokenRefreshSerializer(data={"refresh": raw})
        try:
            ser.is_valid(raise_exception=True)
        except (TokenError, exceptions.ValidationError) as exc:
            response = Response(
                {"error": {"code": "invalid_refresh_token", "message": "Session expired.", "details": {}}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_refresh_cookie(response)
            del exc
            return response
        data = ser.validated_data
        response = Response({"access": data["access"]})
        if "refresh" in data:
            _set_refresh_cookie(response, data["refresh"])
        return response


class LogoutView(PublicAuthView):
    def post(self, request):  # noqa: ANN001, ANN201
        raw = request.COOKIES.get(REFRESH_COOKIE)
        if raw:
            try:
                token = RefreshToken(raw)
                user = User.objects.filter(pk=token["user_id"]).first()
                token.blacklist()
                if user is not None:
                    audit.log("auth.logout", request=request, actor=user, resource_type="user", resource_id=user.pk)
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):  # noqa: ANN001, ANN201
        return Response(MeSerializer(request.user).data)


WS_TICKET_TTL = 30  # seconds
WS_TICKET_PREFIX = "wsticket:"


class WsTicketView(APIView):
    """Single-use, short-lived ticket so the browser can open a WebSocket without putting a JWT in the URL."""

    permission_classes = [IsAuthenticated]

    def post(self, request):  # noqa: ANN001, ANN201
        ticket = secrets.token_urlsafe(24)
        cache.set(f"{WS_TICKET_PREFIX}{ticket}", request.user.pk, WS_TICKET_TTL)
        return Response({"ticket": ticket, "expires_in": WS_TICKET_TTL})
