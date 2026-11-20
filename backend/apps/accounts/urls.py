from django.urls import path
from rest_framework.routers import SimpleRouter

from . import auth_views
from .views import PermissionViewSet, RoleViewSet, UserViewSet

router = SimpleRouter()
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")

urlpatterns = [
    path("auth/login/", auth_views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", auth_views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", auth_views.LogoutView.as_view(), name="auth-logout"),
    path("auth/register/", auth_views.RegisterView.as_view(), name="auth-register"),
    path("auth/verify-email/", auth_views.VerifyEmailView.as_view(), name="auth-verify-email"),
    path("auth/resend-verification/", auth_views.ResendVerificationView.as_view(), name="auth-resend-verification"),
    path("auth/password-reset/", auth_views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "auth/password-reset/confirm/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("auth/me/", auth_views.MeView.as_view(), name="auth-me"),
    path("ws/ticket/", auth_views.WsTicketView.as_view(), name="ws-ticket"),
    *router.urls,
]
