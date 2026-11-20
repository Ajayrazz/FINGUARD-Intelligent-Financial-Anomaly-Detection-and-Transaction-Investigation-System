from django.db import models

from apps.datasets.models import Dataset


class DailyAggregate(models.Model):
    """Per dataset and calendar day (UTC) rollup used by every dashboard series.

    Rebuilt from the transaction tables by `services.refresh_daily_aggregates`, so it is always derivable and never
    authoritative: if it disagrees with the source tables, the source wins and the next refresh repairs it.
    """

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="daily_aggregates")
    date = models.DateField()
    tx_count = models.PositiveIntegerField(default=0)
    tx_value = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    flagged_count = models.PositiveIntegerField(default=0)  # flagged by the dataset's latest succeeded detection run
    by_risk_category = models.JSONField(default=dict)  # latest succeeded risk run: {"high": 3, ...}
    by_type = models.JSONField(default=dict)  # {"TRANSFER": {"count": 5, "value": "100.00"}, ...}
    refreshed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["dataset_id", "date"]
        constraints = [models.UniqueConstraint(fields=["dataset", "date"], name="daily_aggregate_unique")]

    def __str__(self) -> str:
        return f"{self.dataset_id} {self.date}: {self.tx_count} tx"
