from django.db import transaction

from .models import Permission, Role
from .registry import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS, ROLES, SUPER_ADMIN


@transaction.atomic
def seed_roles() -> None:
    """Idempotent. Super Admin always holds every permission; other roles only get defaults for
    permission codenames that did not exist before (so admin edits are preserved)."""
    roles = {}
    for name, (label, description) in ROLES.items():
        role, _ = Role.objects.get_or_create(
            name=name, defaults={"label": label, "description": description, "is_system": True}
        )
        roles[name] = role

    for codename, description in PERMISSIONS.items():
        perm, created = Permission.objects.get_or_create(
            codename=codename, defaults={"description": description}
        )
        if created:
            for role_name, defaults in DEFAULT_ROLE_PERMISSIONS.items():
                if codename in defaults:
                    roles[role_name].permissions.add(perm)

    roles[SUPER_ADMIN].permissions.set(Permission.objects.all())
