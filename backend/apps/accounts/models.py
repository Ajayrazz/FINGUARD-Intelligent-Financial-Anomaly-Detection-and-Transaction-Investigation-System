from __future__ import annotations

from datetime import timedelta
from functools import cached_property
from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

from .registry import SUPER_ADMIN

MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)


class Permission(models.Model):
    codename = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["codename"]

    def __str__(self) -> str:
        return self.codename


class Role(models.Model):
    name = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=80)
    description = models.CharField(max_length=300, blank=True)
    is_system = models.BooleanField(default=False)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.label


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None, role: Role | None = None, **extra: Any) -> User:
        if not email:
            raise ValueError("Email is required")
        if role is None:
            raise ValueError("A role is required")
        extra.setdefault(
            "email_verified_at", timezone.now()
        )  # administrator-created users are trusted; signup passes None
        user = self.model(email=self.normalize_email(email).lower(), role=role, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> User:
        role = Role.objects.get(name=SUPER_ADMIN)
        return self.create_user(email, password, role=role, **extra)


class Approval(models.TextChoices):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


class User(AbstractBaseUser):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users")
    is_active = models.BooleanField(default=True)
    # Self-registration: the address must be confirmed by link and a Super Admin must approve the account.
    # Accounts created by an administrator are approved and verified at creation.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    approval_status = models.CharField(max_length=10, choices=Approval.choices, default=Approval.APPROVED)
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]
    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    # --- authorisation -------------------------------------------------
    @cached_property
    def permission_codenames(self) -> frozenset[str]:
        return frozenset(self.role.permissions.values_list("codename", flat=True))

    @property
    def is_super_admin(self) -> bool:
        return self.role.name == SUPER_ADMIN

    # Django admin integration: only active Super Admins may use /admin/.
    @property
    def is_staff(self) -> bool:
        return self.is_active and self.is_super_admin

    def has_perm(self, perm: str, obj: object = None) -> bool:
        return self.is_active and self.is_super_admin

    def has_module_perms(self, app_label: str) -> bool:
        return self.is_active and self.is_super_admin

    # --- lockout -------------------------------------------------------
    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > timezone.now()

    def register_failed_login(self) -> bool:
        """Returns True if this failure triggered a lockout."""
        self.failed_login_count += 1
        locked = self.failed_login_count >= MAX_FAILED_LOGINS
        if locked:
            self.locked_until = timezone.now() + LOCKOUT
            self.failed_login_count = 0
        self.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
        return locked

    def register_successful_login(self) -> None:
        self.failed_login_count = 0
        self.locked_until = None
        self.last_login = timezone.now()
        self.save(update_fields=["failed_login_count", "locked_until", "last_login", "updated_at"])
