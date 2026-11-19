from datetime import datetime

from django.db import transaction as db_transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.datasets.models import Dataset
from apps.transactions.models import Account, Transaction

from . import services
from .models import BehaviorAnalysisResult, BehaviorRun
from .serializers import BehaviorResultSerializer, BehaviorRunCreateSerializer, BehaviorRunSerializer
from .tasks import run_behavior_task


def _error(code: str, message: str, http_status: int = 400) -> Response:
    return Response({"error": {"code": code, "message": message, "details": {}}}, status=http_status)


def _params(request) -> tuple[datetime, int, str] | Response:  # noqa: ANN001
    q = request.query_params
    as_of = timezone.now()
    if "as_of" in q:
        parsed = parse_datetime(q["as_of"].replace(" ", "+"))  # an unescaped "+" in a URL arrives as a space
        if parsed is None:
            return _error("validation_error", "as_of must be an ISO-8601 timestamp.")
        as_of = parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    try:
        window = int(q.get("window_days", services.CFG["window_days"]))
    except ValueError:
        return _error("validation_error", "window_days must be an integer.")
    if not 1 <= window <= 365:
        return _error("validation_error", "window_days must be between 1 and 365.")
    direction = q.get("direction", "out")
    if direction not in ("out", "in"):
        return _error("validation_error", "direction must be out or in.")
    return as_of, window, direction


class AccountBehaviorProfileView(APIView):
    """Profile of an account's spending as of a point in time (live, strictly earlier transactions only)."""

    required_permissions = {"GET": "behavior.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        parsed = _params(request)
        if isinstance(parsed, Response):
            return parsed
        as_of, window, direction = parsed
        return Response(services.live_profile(get_object_or_404(Account, pk=pk), as_of, window, direction))


class AccountBehaviorTrendsView(APIView):
    required_permissions = {"GET": "behavior.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        parsed = _params(request)
        if isinstance(parsed, Response):
            return parsed
        as_of, window, direction = parsed
        try:
            data = services.live_trends(
                get_object_or_404(Account, pk=pk),
                as_of,
                window,
                request.query_params.get("granularity", "day"),
                direction,
            )
        except services.BehaviorError as exc:
            return _error("validation_error", str(exc))
        return Response(data)


class TransactionBehaviorView(APIView):
    """Behavioral deviation of one transaction against its sender's history before it, with a component breakdown."""

    required_permissions = {"GET": "behavior.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        tx = get_object_or_404(Transaction.objects.select_related("sender", "receiver"), pk=pk)
        return Response(services.live_transaction_behavior(tx))


class BehaviorRunViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = BehaviorRun.objects.select_related("dataset", "created_by")
    serializer_class = BehaviorRunSerializer
    required_permissions = {"list": "behavior.read", "retrieve": "behavior.read", "create": "behavior.run",
                            "results": "behavior.read"}  # fmt: skip

    def create(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        ser = BehaviorRunCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dataset = Dataset.objects.filter(pk=ser.validated_data["dataset"]).first()
        if dataset is None:
            return _error("validation_error", "Unknown dataset.")
        try:
            run = services.create_run(dataset=dataset, user=request.user)
        except services.BehaviorError as exc:
            return _error("behavior_not_possible", str(exc))
        db_transaction.on_commit(lambda: run_behavior_task.delay(run.pk))
        return Response(BehaviorRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"], url_path="results")
    def results(self, request, pk=None):  # noqa: ANN001, ANN201
        """Highest deviation first. `?status=scored|unavailable_cold_start`; `?min_score=`."""
        run = self.get_object()
        qs = BehaviorAnalysisResult.objects.filter(run=run).select_related("account", "transaction")
        st = request.query_params.get("status")
        if st in ("scored", "unavailable_cold_start"):
            qs = qs.filter(status=st)
        if "min_score" in request.query_params:
            try:
                qs = qs.filter(deviation_score__gte=float(request.query_params["min_score"]))
            except ValueError:
                return _error("validation_error", "min_score must be a number.")
        qs = qs.order_by(F("deviation_score").desc(nulls_last=True), "id")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(BehaviorResultSerializer(page, many=True).data)
