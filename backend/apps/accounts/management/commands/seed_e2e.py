"""Seed the isolated end-to-end database: one user per role and a small, clearly synthetic investigation scenario.

Refuses to run unless the database name ends in `_e2e` and DEBUG is on, so it can never touch real data.
    E2E_PASSWORD=... python manage.py seed_e2e
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.accounts.registry import ROLES

PREFIX = "e2e-"


class Command(BaseCommand):
    help = "Create role users and demo data for the browser test stack (database must be *_e2e)."

    def handle(self, *args, **opts):
        db = settings.DATABASES["default"]["NAME"]
        if not str(db).endswith("_e2e") or not settings.DEBUG:
            raise CommandError(f"Refusing to seed '{db}': only a *_e2e database with DEBUG on is allowed.")
        password = os.environ.get("E2E_PASSWORD", "")
        if len(password) < 12:
            raise CommandError("Set E2E_PASSWORD (at least 12 characters).")
        for name in ROLES:
            if name == "pending_user":
                continue  # the no-access role is only for self-registered users, seeded below
            email = f"{PREFIX}{name.replace('_', '-')}@example.com"
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={"full_name": f"E2E {name.replace('_', ' ').title()}", "role": Role.objects.get(name=name)},
            )
            user.role = Role.objects.get(name=name)
            user.is_active, user.failed_login_count, user.locked_until = True, 0, None
            user.email_verified_at, user.approval_status = timezone.now(), "approved"
            user.set_password(password)
            user.save()
            self.stdout.write(f"user {email} ({name})")
        self._signup_users(password)
        self._demo_data()

    def _signup_users(self, password: str) -> None:
        """Self-registration states for the browser tests. Re-seeding puts both back to their starting state."""
        no_access = Role.objects.get(name="pending_user")
        for email, verified in ((f"{PREFIX}pending@example.com", True), (f"{PREFIX}unverified@example.com", False)):
            user, _ = User.objects.get_or_create(
                email=email, defaults={"full_name": "E2E Self Registered", "role": no_access}
            )
            user.role, user.is_active, user.approval_status = no_access, True, "pending"
            user.email_verified_at = timezone.now() if verified else None
            user.failed_login_count, user.locked_until = 0, None
            user.set_password(password)
            user.save()
            self.stdout.write(
                f"user {email} (self-registered, {'email confirmed' if verified else 'email NOT confirmed'}, pending)"
            )

    def _demo_data(self):
        from apps.alerts import services as alert_services
        from apps.behavior import scenario as behavior_scenario
        from apps.behavior import services as behavior_services
        from apps.datasets.models import Dataset
        from apps.duplicates import services as dup_services
        from apps.duplicates.models import DuplicateScanRun
        from apps.graph_engine import scenario as graph_scenario
        from apps.graph_engine import services as graph_services
        from apps.risk_engine import services as risk_services

        admin = User.objects.get(email=f"{PREFIX}super-admin@example.com")
        if Dataset.objects.filter(name="DEMO E2E behaviour (synthetic)").exists():
            self.stdout.write("demo data already present")
            return
        ds = behavior_scenario.build("DEMO E2E behaviour (synthetic)")
        brun = behavior_services.create_run(dataset=ds, user=admin)
        behavior_services.execute_run(brun.pk)
        snap = graph_services.create_snapshot(dataset=ds, user=admin, as_of=None, window_days=None)
        graph_services.execute_snapshot(snap.pk)
        scan = DuplicateScanRun.objects.create(kind="transaction", dataset=ds, created_by=admin)
        dup_services.execute_scan(scan.pk)
        risk = risk_services.start_run(dataset=ds, user=admin)
        risk_services.execute_run(risk.pk)
        run = alert_services.start_run(dataset=ds, user=admin)
        alert_services.execute_run(run.pk)
        g = graph_scenario.build("DEMO E2E graph (synthetic)")
        gs = graph_services.create_snapshot(dataset=g, user=admin, as_of=None, window_days=None)
        graph_services.execute_snapshot(gs.pk)
        self.stdout.write(f"demo data created: {ds.name} (alerts + auto cases), {g.name}")
