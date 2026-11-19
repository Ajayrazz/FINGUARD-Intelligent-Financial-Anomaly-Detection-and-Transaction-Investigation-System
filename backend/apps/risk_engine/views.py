from django.db import transaction as db_transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.datasets.models import Dataset
from apps.model_registry.models import ModelVersion
from apps.transactions.models import Account, Transaction
from risk_engine_lib import COMPONENTS

from . import services
from .models import AccountRiskHistory, RiskAssessment, RiskConfig, RiskScoreRun
from .serializers import (
    AccountRiskHistorySerializer,
    AssessmentDetailSerializer,
    AssessmentListSerializer,
    RiskConfigCreateSerializer,
    RiskConfigSerializer,
    RiskRunCreateSerializer,
    RiskRunSerializer,
)
from .tasks import run_scoring_task


def _error(code: str, message: str, http_status: int = 400) -> Response:
    return Response({"error": {"code": code, "message": message, "details": {}}}, status=http_status)


class RiskAssessmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = RiskAssessment.objects.select_related("transaction", "account", "config")
    required_permissions = {"list": "risk.read", "retrieve": "risk.read"}

    def get_serializer_class(self):  # noqa: ANN201
        return AssessmentDetailSerializer if self.action == "retrieve" else AssessmentListSerializer

    def get_queryset(self):  # noqa: ANN201
        qs = super().get_queryset()
        q = self.request.query_params
        for key in ("transaction", "account", "category", "run"):
            if q.get(key):
                qs = qs.filter(**{key: q[key]} if key in ("category",) else {f"{key}_id": q[key]})
        if q.get("min_score"):
            try:
                qs = qs.filter(overall_score__gte=float(q["min_score"]))
            except ValueError:
                pass
        if q.get("scored") == "true":
            qs = qs.exclude(overall_score=None)
        return qs.order_by(F("overall_score").desc(nulls_last=True), "id")


class RiskRunViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = RiskScoreRun.objects.select_related("dataset", "config", "created_by")
    serializer_class = RiskRunSerializer
    required_permissions = {"list": "risk.read", "retrieve": "risk.read", "create": "risk.run"}

    def create(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        ser = RiskRunCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        dataset = Dataset.objects.filter(pk=v["dataset"]).first()
        if dataset is None:
            return _error("validation_error", "Unknown dataset.")
        cfg = None
        if "config" in v:
            cfg = RiskConfig.objects.filter(pk=v["config"]).first()
            if cfg is None:
                return _error("validation_error", "Unknown risk configuration.")
        try:
            run = services.start_run(dataset=dataset, user=request.user, config=cfg)
        except services.RiskError as exc:
            return _error("risk_not_possible", str(exc))
        db_transaction.on_commit(lambda: run_scoring_task.delay(run.pk))
        return Response(RiskRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


class RiskConfigViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """Weights, thresholds and missing-signal policy are versioned: there is no edit, only a new version."""

    queryset = RiskConfig.objects.select_related("created_by", "model_version")
    serializer_class = RiskConfigSerializer
    pagination_class = None
    required_permissions = {
        "list": "risk.read",
        "retrieve": "risk.read",
        "create": "risk.configure",
        "activate": "risk.configure",
    }

    def create(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        ser = RiskConfigCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        mv = None
        if v.get("model_version"):
            mv = ModelVersion.objects.filter(pk=v["model_version"]).first()
            if mv is None:
                return _error("validation_error", "Unknown model version.")
        try:
            cfg = services.create_config(user=request.user, weights=v["weights"], thresholds=v["thresholds"], policy=v["missing_signal_policy"],
                                         min_coverage=v["min_coverage"], model_version=mv, notes=v["notes"])  # fmt: skip
        except services.RiskError as exc:
            return _error("invalid_config", str(exc))
        return Response(RiskConfigSerializer(cfg).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="activate", parser_classes=[JSONParser])
    def activate(self, request, pk=None):  # noqa: ANN001, ANN201
        cfg = services.activate_config(self.get_object(), request.user)
        return Response(RiskConfigSerializer(cfg).data)


class TransactionRiskView(APIView):
    """Latest assessment of a transaction (404 if it has never been scored)."""

    required_permissions = {"GET": "risk.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        get_object_or_404(Transaction, pk=pk)
        a = (
            RiskAssessment.objects.filter(transaction_id=pk)
            .select_related("transaction", "account", "config")
            .order_by("-computed_at", "-id")
            .first()
        )
        if a is None:
            return _error("not_found", "This transaction has not been scored.", 404)
        return Response(AssessmentDetailSerializer(a).data)


class TransactionRiskHistoryView(ListAPIView):
    serializer_class = AssessmentListSerializer
    required_permissions = {"GET": "risk.read"}

    def get_queryset(self):  # noqa: ANN201
        return (
            RiskAssessment.objects.filter(transaction_id=self.kwargs["pk"])
            .select_related("transaction", "account", "config")
            .order_by("-computed_at", "-id")
        )


class AccountRiskHistoryView(APIView):
    """Account-level risk snapshots (Medium and above) plus the account's most recent assessments."""

    required_permissions = {"GET": "risk.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        acct = get_object_or_404(Account, pk=pk)
        hist = AccountRiskHistory.objects.filter(account=acct).order_by("-as_of")[:50]
        recent = (
            RiskAssessment.objects.filter(account=acct)
            .exclude(overall_score=None)
            .select_related("transaction", "account", "config")
            .order_by("-overall_score")[:10]
        )
        return Response({"account": acct.pk, "account_ref": acct.account_ref, "history": AccountRiskHistorySerializer(hist, many=True).data,
                         "highest_assessments": AssessmentListSerializer(recent, many=True).data})  # fmt: skip


class RiskCompareView(APIView):
    """Compare two assessments component by component (e.g. two config versions, or before/after a new signal)."""

    required_permissions = {"GET": "risk.read"}

    def get(self, request):  # noqa: ANN001, ANN201
        try:
            a_id, b_id = int(request.query_params["a"]), int(request.query_params["b"])
        except (KeyError, ValueError):
            return _error("validation_error", "Pass integer assessment ids as a and b.")
        a = RiskAssessment.objects.filter(pk=a_id).select_related("config", "transaction").first()
        b = RiskAssessment.objects.filter(pk=b_id).select_related("config", "transaction").first()
        if a is None or b is None:
            return _error("not_found", "Assessment not found.", 404)

        def side(x: RiskAssessment) -> dict:
            return {"id": x.pk, "transaction": x.transaction_id, "overall_score": x.overall_score, "category": x.category,
                    "weight_coverage": x.weight_coverage, "config_version": x.config.version, "algorithm_version": x.algorithm_version,
                    "computed_at": x.computed_at}  # fmt: skip

        diff = {}
        for c in COMPONENTS:
            ca, cb = a.components.get(c, {}), b.components.get(c, {})
            va, vb = (
                (ca.get("value") if ca.get("available") else None),
                (cb.get("value") if cb.get("available") else None),
            )
            diff[c] = {"a": va, "b": vb, "delta": (vb - va) if va is not None and vb is not None else None}
        comparable = a.config_id == b.config_id and a.algorithm_version == b.algorithm_version
        return Response({"a": side(a), "b": side(b), "components": diff, "comparable": comparable,
                         "note": None if comparable else "Different configuration or algorithm version: scores are not directly comparable."})  # fmt: skip
