import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.accounts.seed import seed_roles
from apps.audit import services as audit


class Command(BaseCommand):
    help = "Create the first Super Admin. Password from FINGUARD_ADMIN_PASSWORD or an interactive prompt."

    def add_arguments(self, parser):  # noqa: ANN001, ANN201
        parser.add_argument("--email", required=True)
        parser.add_argument("--full-name", default="Super Admin")

    def handle(self, *args, **opts):  # noqa: ANN002, ANN003, ANN201
        seed_roles()
        email = opts["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("A user with that email already exists.")
        password = os.environ.get("FINGUARD_ADMIN_PASSWORD") or getpass.getpass("Password: ")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        user = User.objects.create_superuser(email, password, full_name=opts["full_name"])
        audit.log("user.created", actor=None, actor_email="system:create_superadmin", resource_type="user",
                  resource_id=user.pk, changes={"email": user.email, "role": "super_admin"})  # fmt: skip
        self.stdout.write(self.style.SUCCESS(f"Created Super Admin {user.email}"))
