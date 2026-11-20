from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit import services as audit

from . import services
from .models import Permission, Role, User
from .serializers import (
    ApproveSerializer,
    PasswordResetSerializer,
    PermissionSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """No DELETE: users are deactivated, never deleted (audit integrity)."""

    queryset = User.objects.select_related("role").all()
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["role__name", "is_active", "approval_status"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["email", "full_name"]
    ordering_fields = ["email", "full_name", "created_at", "last_login"]
    required_permissions = {
        "list": "users.read",
        "retrieve": "users.read",
        "create": "users.create",
        "partial_update": "users.update",
        "reset_password": "users.update",
        "approve": "users.update",
        "reject": "users.update",
    }

    def get_serializer_class(self):  # noqa: ANN201
        if self.action == "create":
            return UserCreateSerializer
        if self.action == "partial_update":
            return UserUpdateSerializer
        if self.action == "reset_password":
            return PasswordResetSerializer
        if self.action == "approve":
            return ApproveSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.create_user(actor=request.user, request=request, validated=ser.validated_data)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        user = self.get_object()
        ser = self.get_serializer(user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        user = services.update_user(actor=request.user, request=request, user=user, validated=ser.validated_data)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):  # noqa: ANN001, ANN201
        user = self.get_object()
        ser = self.get_serializer(data=request.data, context={**self.get_serializer_context(), "target_user": user})
        ser.is_valid(raise_exception=True)
        services.reset_password(
            actor=request.user, request=request, user=user, new_password=ser.validated_data["new_password"]
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):  # noqa: ANN001, ANN201
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.approve_user(
            actor=request.user, request=request, user=self.get_object(), role=ser.validated_data["role"]
        )
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):  # noqa: ANN001, ANN201
        user = services.reject_user(actor=request.user, request=request, user=self.get_object())
        return Response(UserSerializer(user).data)


class RoleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]
    required_permissions = {
        "list": "roles.read",
        "retrieve": "roles.read",
        "create": "roles.create",
        "partial_update": "roles.update",
    }

    def perform_create(self, serializer: RoleSerializer) -> None:  # type: ignore[override]
        role = serializer.save(is_system=False)
        audit.log(
            "role.created", request=self.request, resource_type="role", resource_id=role.pk,
            changes={"name": role.name, "permissions": sorted(p.codename for p in role.permissions.all())},
        )  # fmt: skip

    def perform_update(self, serializer: RoleSerializer) -> None:  # type: ignore[override]
        assert serializer.instance is not None
        before = sorted(p.codename for p in serializer.instance.permissions.all())
        role = serializer.save()
        after = sorted(p.codename for p in role.permissions.all())
        audit.log(
            "role.updated", request=self.request, resource_type="role", resource_id=role.pk,
            changes={"permissions": {"from": before, "to": after}},
        )  # fmt: skip


class PermissionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    pagination_class = None
    required_permissions = {"list": "roles.read"}
