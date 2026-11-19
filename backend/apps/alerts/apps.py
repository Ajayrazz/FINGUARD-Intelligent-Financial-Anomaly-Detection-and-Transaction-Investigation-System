from django.apps import AppConfig


class AlertsConfig(AppConfig):
    name = "apps.alerts"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from django.db.models.signals import post_save

        from apps.risk_engine.models import RiskScoreRun

        from .signals import on_risk_run_saved

        post_save.connect(on_risk_run_saved, sender=RiskScoreRun, dispatch_uid="alerts_on_risk_run")
