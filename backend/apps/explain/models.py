from django.conf import settings
from django.db import models

from apps.detection.models import Prediction
from apps.model_registry.models import ModelVersion
from apps.risk_engine.models import RiskAssessment
from apps.transactions.models import Transaction


class ExplanationJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    transaction = models.ForeignKey(
        Transaction, null=True, blank=True, on_delete=models.PROTECT, related_name="explanation_jobs"
    )
    model_version = models.ForeignKey(ModelVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=12, default="transaction")  # transaction | global
    methods = models.JSONField(default=list)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(default=dict)  # {"created": [...], "skipped": {method: reason}}
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"explanation job {self.pk}"


class Explanation(models.Model):
    """One stored explanation, tied to the exact model version, prediction and risk assessment it explains."""

    class Method(models.TextChoices):
        SHAP = "shap"
        LIME = "lime"
        FEATURE_IMPORTANCE = "feature_importance"
        BEHAVIORAL = "behavioral"
        GRAPH = "graph"
        RISK_BREAKDOWN = "risk_breakdown"
        SUMMARY = "summary"

    transaction = models.ForeignKey(
        Transaction, null=True, blank=True, on_delete=models.PROTECT, related_name="explanations"
    )
    prediction = models.ForeignKey(
        Prediction, null=True, blank=True, on_delete=models.PROTECT, related_name="explanations"
    )
    assessment = models.ForeignKey(
        RiskAssessment, null=True, blank=True, on_delete=models.PROTECT, related_name="explanations"
    )
    model_version = models.ForeignKey(
        ModelVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="explanations"
    )
    method = models.CharField(max_length=20, choices=Method.choices)
    payload = models.JSONField(default=dict)
    narrative = models.TextField(blank=True)
    generator_version = models.CharField(max_length=10)
    job = models.ForeignKey(
        ExplanationJob, null=True, blank=True, on_delete=models.SET_NULL, related_name="explanations"
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-generated_at", "-id"]
        indexes = [models.Index(fields=["transaction", "method", "-generated_at"], name="expl_tx_method_idx")]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(method__in=["shap", "lime"])
                | (models.Q(prediction__isnull=False) & models.Q(model_version__isnull=False)),
                name="model_explanation_needs_prediction_and_version",
            ),
            models.CheckConstraint(
                condition=~models.Q(method="risk_breakdown") | models.Q(assessment__isnull=False),
                name="risk_explanation_needs_assessment",
            ),
            models.CheckConstraint(
                condition=~models.Q(method="feature_importance") | models.Q(model_version__isnull=False),
                name="importance_needs_model_version",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.method} explanation {self.pk}"
