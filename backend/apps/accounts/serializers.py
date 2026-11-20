from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Permission, Role, User
from .registry import PENDING_USER, SUPER_ADMIN


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["codename", "description"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        many=True, slug_field="codename", queryset=Permission.objects.all(), required=False
    )

    class Meta:
        model = Role
        fields = ["id", "name", "label", "description", "is_system", "permissions"]
        read_only_fields = ["id", "is_system"]

    def validate_name(self, value: str) -> str:
        if self.instance is not None and value != self.instance.name:
            raise serializers.ValidationError("Role name cannot be changed.")
        return value

    def validate(self, attrs):  # noqa: ANN001, ANN201
        if self.instance is not None and self.instance.name == SUPER_ADMIN and "permissions" in attrs:
            raise serializers.ValidationError({"permissions": "Super Admin permissions cannot be changed."})
        return attrs


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(slug_field="name", queryset=Role.objects.all())
    role_label = serializers.CharField(source="role.label", read_only=True)
    email_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "role_label",
            "is_active",
            "approval_status",
            "email_verified",
            "last_login",
            "created_at",
        ]
        read_only_fields = ["id", "approval_status", "email_verified", "last_login", "created_at"]

    def get_email_verified(self, obj: User) -> bool:
        return obj.is_email_verified


class UserCreateSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta(UserSerializer.Meta):
        fields = [*UserSerializer.Meta.fields, "password"]

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):  # noqa: ANN001, ANN201
        validate_password(attrs["password"], user=User(email=attrs["email"], full_name=attrs["full_name"]))
        return attrs


class UserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(slug_field="name", queryset=Role.objects.all(), required=False)

    class Meta:
        model = User
        fields = ["full_name", "role", "is_active"]


class PasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        validate_password(value, user=self.context.get("target_user"))
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class MeSerializer(UserSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = [*UserSerializer.Meta.fields, "permissions"]

    def get_permissions(self, obj: User) -> list[str]:
        return sorted(obj.permission_codenames)


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    full_name = serializers.CharField(min_length=2, max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    accept_terms = serializers.BooleanField()

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_full_name(self, value: str) -> str:
        return " ".join(value.split())

    def validate_accept_terms(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("You must accept the terms to create an account.")
        return value

    def validate(self, attrs):  # noqa: ANN001, ANN201
        # Same checks whether or not the address is already registered, so the response never reveals that.
        try:
            validate_password(attrs["password"], user=User(email=attrs["email"], full_name=attrs["full_name"]))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=500)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=50)
    token = serializers.CharField(max_length=200)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class ApproveSerializer(serializers.Serializer):
    role = serializers.SlugRelatedField(slug_field="name", queryset=Role.objects.exclude(name=PENDING_USER))
