from django.apps import AppConfig


class CasesConfig(AppConfig):
    name = "apps.cases"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.alerts.signals import alert_created, alert_raised

        from .services import on_alert_created

        alert_created.connect(on_alert_created, dispatch_uid="cases_on_alert_created")
        alert_raised.connect(on_alert_created, dispatch_uid="cases_on_alert_raised")
