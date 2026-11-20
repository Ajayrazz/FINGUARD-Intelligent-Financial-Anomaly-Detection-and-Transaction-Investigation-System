from datetime import date

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit import services as audit
from apps.datasets.models import Dataset

from . import services


def _bad(message: str) -> Response:
    return Response(
        {"error": {"code": "validation_error", "message": message, "details": {}}}, status=status.HTTP_400_BAD_REQUEST
    )


def _date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


class AnalyticsViewSet(viewsets.GenericViewSet):
    """Read-only analytics. Every number comes from `services` (stored rows), filtered by dataset and date range."""

    queryset = Dataset.objects.none()
    pagination_class = None
    required_permissions = {
        "datasets": "analytics.read", "overview": "analytics.read", "volume": "analytics.read", "risk_distribution": "analytics.read",  # noqa: E501
        "high_risk_accounts": "analytics.read", "recent_suspicious": "analytics.read", "investigations_summary": "analytics.read",  # noqa: E501
        "false_positives": "analytics.read", "detection_performance": "analytics.read", "export": "analytics.export", "refresh": "analytics.refresh",  # noqa: E501
    }  # fmt: skip

    def _filters(self, request):  # noqa: ANN001, ANN202
        q = request.query_params
        try:
            ds = int(q["dataset"]) if q.get("dataset") else None
            d_from, d_to = _date(q.get("from")), _date(q.get("to"))
        except ValueError:
            return None, "Invalid dataset or date (dates are YYYY-MM-DD)."
        if ds is not None and not Dataset.objects.filter(pk=ds).exists():
            return None, "Unknown dataset."
        return (ds, d_from, d_to), None

    def _run(self, request, fn):  # noqa: ANN001, ANN002, ANN202
        f, err = self._filters(request)
        return _bad(err) if err else Response(fn(*f))

    @action(detail=False, methods=["get"], url_path="datasets")
    def datasets(self, request):  # noqa: ANN001, ANN201
        """Id and name only, so roles without dataset access can still filter analytics."""
        return Response(list(Dataset.objects.order_by("name").values("id", "name")))

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):  # noqa: ANN001, ANN201
        return self._run(request, lambda ds, a, b: services.overview(ds))

    @action(detail=False, methods=["get"], url_path="volume")
    def volume(self, request):  # noqa: ANN001, ANN201
        gran = request.query_params.get("granularity", "day")
        if gran not in services.GRANULARITIES:
            return _bad("granularity must be day, week or month.")
        return self._run(request, lambda ds, a, b: {"granularity": gran, "series": services.volume(ds, gran, a, b)})

    @action(detail=False, methods=["get"], url_path="risk-distribution")
    def risk_distribution(self, request):  # noqa: ANN001, ANN201
        return self._run(request, lambda ds, a, b: services.risk_distribution(ds))

    @action(detail=False, methods=["get"], url_path="accounts/high-risk")
    def high_risk_accounts(self, request):  # noqa: ANN001, ANN201
        return self._run(request, lambda ds, a, b: services.high_risk_accounts(ds))

    @action(detail=False, methods=["get"], url_path="recent-suspicious")
    def recent_suspicious(self, request):  # noqa: ANN001, ANN201
        return self._run(request, lambda ds, a, b: services.recent_suspicious(ds))

    @action(detail=False, methods=["get"], url_path="investigations/summary")
    def investigations_summary(self, request):  # noqa: ANN001, ANN201
        return self._run(request, services.investigations_summary)

    @action(detail=False, methods=["get"], url_path="false-positives")
    def false_positives(self, request):  # noqa: ANN001, ANN201
        return self._run(request, lambda ds, a, b: services.false_positives(ds))

    @action(detail=False, methods=["get"], url_path="detection-performance")
    def detection_performance(self, request):  # noqa: ANN001, ANN201
        return Response(services.detection_performance())

    @action(detail=False, methods=["post"], url_path="refresh")
    def refresh(self, request):  # noqa: ANN001, ANN201
        f, err = self._filters(request)
        if err:
            return _bad(err)
        ds = f[0]
        done = {ds: services.refresh_daily_aggregates(ds)} if ds else services.refresh_all()
        audit.log(
            "analytics.refreshed",
            request=request,
            resource_type="analytics",
            resource_id=ds or "all",
            changes={"days": done},
        )
        return Response({"refreshed_datasets": len(done), "days": sum(done.values())})

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):  # noqa: ANN001, ANN201
        report, fmt = (
            request.query_params.get("report", ""),
            request.query_params.get("file", "csv"),
        )  # not "format": DRF reserves it
        if report not in services.REPORTS:
            return _bad(f"report must be one of: {', '.join(services.REPORTS)}.")
        if fmt not in ("csv", "pdf"):
            return _bad("file must be csv or pdf.")
        gran = request.query_params.get("granularity", "day")
        if gran not in services.GRANULARITIES:
            return _bad("granularity must be day, week or month.")
        f, err = self._filters(request)
        if err:
            return _bad(err)
        ds, d_from, d_to = f
        title, headers, rows = services.report_table(report, ds, gran, d_from, d_to)
        audit.log(
            "analytics.exported",
            request=request,
            resource_type="analytics",
            resource_id=report,
            changes={"format": fmt, "dataset": ds, "rows": len(rows)},
        )
        stamp = services.now().strftime("%Y%m%d")
        if fmt == "pdf":
            subtitle = f"Dataset: {ds or 'all'} · period: {d_from or 'start'} to {d_to or 'now'}"
            resp = HttpResponse(services.to_pdf(title, subtitle, headers, rows), content_type="application/pdf")
        else:
            resp = HttpResponse(services.to_csv(headers, rows), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="finguard-{report}-{stamp}.{fmt}"'
        return resp
