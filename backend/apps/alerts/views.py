from django.db import transaction as db_transaction
from django.db.models import Case, Count, IntegerField, Value, When
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.datasets.models import Dataset
from apps.transactions.models import Transaction

from . import services
from .models import Alert, AlertPolicy, AlertRun
from .serializers import (
    AlertDetailSerializer,
    AlertEventSerializer,
    AlertRunSerializer,
    AlertSerializer,
    AssignSerializer,
    CloseSerializer,
    EscalateSerializer,
    EvaluateSerializer,
    NotificationSerializer,
    PolicyCreateSerializer,
    PolicySerializer,
)
from .tasks import evaluate_task


def _error(code: str, message: str, http_status: int = 400) -> Response:
    return Response({"error": {"code": code, "message": message, "details": {}}}, status=http_status)


SEVERITY_ORDER = Case(
    When(severity="critical", then=Value(3)),
    When(severity="high", then=Value(2)),
    When(severity="medium", then=Value(1)),
    default=Value(0),
    output_field=IntegerField(),
)


class AlertViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Alert.objects.select_related("transaction", "account", "assignee", "assessment", "dataset")
    required_permissions = {"list": "alerts.read", "retrieve": "alerts.read", "events": "alerts.read", "notifications": "alerts.read", "acknowledge": "alerts.acknowledge",
                            "assign": "alerts.assign", "escalate": "alerts.escalate", "close": "alerts.close", "summary": "alerts.summary", "assignees": "alerts.assign"}  # fmt: skip

    def get_serializer_class(self):  # noqa: ANN201
        return AlertDetailSerializer if self.action == "retrieve" else AlertSerializer

    def get_queryset(self):  # noqa: ANN201
        qs = super().get_queryset()
        q = self.request.query_params
        for key in ("status", "severity", "alert_type", "dataset", "transaction", "account"):
            if q.get(key):
                qs = qs.filter(**{key: q[key]})
        if q.get("assignee") == "me":
            qs = qs.filter(assignee=self.request.user)
        elif q.get("assignee") == "none":
            qs = qs.filter(assignee__isnull=True)
        elif q.get("assignee"):
            qs = qs.filter(assignee_id=q["assignee"])
        if q.get("category"):
            qs = qs.filter(assessment__category=q["category"])
        for key, field in (("created_after", "created_at__gte"), ("created_before", "created_at__lte")):
            if q.get(key):
                qs = qs.filter(**{field: q[key].replace(" ", "+")})
        if q.get("open") == "true":
            qs = qs.exclude(status="closed")
        # prioritisation: open before closed, then severity, then the risk score behind it, then newest
        return qs.annotate(
            _sev=SEVERITY_ORDER,
            _open=Case(When(status="closed", then=Value(0)), default=Value(1), output_field=IntegerField()),
        ).order_by("-_open", "-_sev", "-assessment__overall_score", "-created_at", "-id")

    def _act(self, request, fn, *args):  # noqa: ANN001, ANN002, ANN202
        try:
            return Response(AlertDetailSerializer(fn(self.get_object(), request.user, *args)).data)
        except services.AlertError as exc:
            return _error("invalid_transition", str(exc), 409)

    @action(detail=True, methods=["post"], url_path="acknowledge", parser_classes=[JSONParser])
    def acknowledge(self, request, pk=None):  # noqa: ANN001, ANN201
        return self._act(request, services.acknowledge)

    @action(detail=True, methods=["post"], url_path="assign", parser_classes=[JSONParser])
    def assign(self, request, pk=None):  # noqa: ANN001, ANN201
        ser = AssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        assignee = services.eligible_assignees().filter(pk=ser.validated_data["assignee"]).first()
        if assignee is None:
            return _error("validation_error", "That user cannot be assigned alerts.")
        return self._act(request, services.assign, assignee)

    @action(detail=True, methods=["post"], url_path="escalate", parser_classes=[JSONParser])
    def escalate(self, request, pk=None):  # noqa: ANN001, ANN201
        ser = EscalateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return self._act(request, services.escalate, ser.validated_data["reason"])

    @action(detail=True, methods=["post"], url_path="close", parser_classes=[JSONParser])
    def close(self, request, pk=None):  # noqa: ANN001, ANN201
        ser = CloseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return self._act(request, services.close, ser.validated_data["outcome"], ser.validated_data["notes"])

    @action(detail=True, methods=["get"], url_path="events")
    def events(self, request, pk=None):  # noqa: ANN001, ANN201
        return Response(AlertEventSerializer(self.get_object().events.select_related("actor"), many=True).data)

    @action(detail=True, methods=["get"], url_path="notifications")
    def notifications(self, request, pk=None):  # noqa: ANN001, ANN201
        return Response(NotificationSerializer(self.get_object().notifications.all(), many=True).data)

    @action(detail=False, methods=["get"], url_path="summary", pagination_class=None)
    def summary(self, request):  # noqa: ANN001, ANN201
        """Counts only (no records): what the Management role may see."""
        rows = Alert.objects.exclude(status="closed").values("severity").annotate(n=Count("id"))
        by_sev = {r["severity"]: r["n"] for r in rows}
        by_status = {r["status"]: r["n"] for r in Alert.objects.values("status").annotate(n=Count("id"))}
        return Response({"open_by_severity": {s: by_sev.get(s, 0) for s in ("critical", "high", "medium", "low")}, "by_status": by_status,
                         "unassigned_open": Alert.objects.exclude(status="closed").filter(assignee__isnull=True).count()})  # fmt: skip

    @action(detail=False, methods=["get"], url_path="assignees", pagination_class=None)
    def assignees(self, request):  # noqa: ANN001, ANN201
        return Response(
            [{"id": u.pk, "email": u.email, "full_name": u.full_name} for u in services.eligible_assignees()]
        )


class EvaluateView(APIView):
    """Run the alert rules over a dataset's stored results (risk, behaviour, graph, duplicates). Returns 202."""

    required_permissions = {"POST": "alerts.run"}

    def post(self, request):  # noqa: ANN001, ANN201
        ser = EvaluateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dataset = Dataset.objects.filter(pk=ser.validated_data["dataset"]).first()
        if dataset is None:
            return _error("validation_error", "Unknown dataset.")
        try:
            run = services.start_run(dataset=dataset, user=request.user)
        except services.AlertError as exc:
            return _error("alerts_not_possible", str(exc))
        db_transaction.on_commit(lambda: evaluate_task.delay(run.pk))
        return Response(AlertRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


class AlertRunListView(ListAPIView):
    queryset = AlertRun.objects.select_related("dataset")
    serializer_class = AlertRunSerializer
    required_permissions = {"GET": "alerts.read"}


class PolicyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = AlertPolicy.objects.select_related("created_by")
    serializer_class = PolicySerializer
    pagination_class = None
    required_permissions = {
        "list": "alerts.read",
        "retrieve": "alerts.read",
        "create": "alerts.configure",
        "activate": "alerts.configure",
    }

    def create(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        ser = PolicyCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            pol = services.create_policy(
                user=request.user, settings_dict=ser.validated_data["config"], notes=ser.validated_data["notes"]
            )
        except services.AlertError as exc:
            return _error("invalid_policy", str(exc))
        return Response(PolicySerializer(pol).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="activate", parser_classes=[JSONParser])
    def activate(self, request, pk=None):  # noqa: ANN001, ANN201
        return Response(PolicySerializer(services.activate_policy(self.get_object(), request.user)).data)


class TransactionAlertsView(ListAPIView):
    serializer_class = AlertSerializer
    pagination_class = None
    required_permissions = {"GET": "alerts.read"}

    def get_queryset(self):  # noqa: ANN201
        get_object_or_404(Transaction, pk=self.kwargs["pk"])
        return (
            Alert.objects.filter(transaction_id=self.kwargs["pk"])
            .select_related("transaction", "account", "assignee", "assessment", "dataset")
            .order_by("-created_at")
        )
