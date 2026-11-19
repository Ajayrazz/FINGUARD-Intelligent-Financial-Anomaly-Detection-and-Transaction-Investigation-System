from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Permission, Role, User
from .registry import SUPER_ADMIN


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

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "role_label", "is_active", "last_login", "created_at"]
        read_only_fields = ["id", "last_login", "created_at"]


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
