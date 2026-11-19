from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _seed(sender, **kwargs):  # noqa: ANN001
    from .seed import seed_roles

    seed_roles()


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"

    def ready(self) -> None:
        post_migrate.connect(_seed, sender=self)
