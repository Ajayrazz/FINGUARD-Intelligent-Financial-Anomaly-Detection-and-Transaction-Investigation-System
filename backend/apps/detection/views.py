from django.db import transaction as db_transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from apps.datasets.models import Dataset

from . import services
from .models import DetectionRun, Prediction
from .serializers import (
    DetectionRunCreateSerializer,
    DetectionRunSerializer,
    PredictionSerializer,
    TransactionPredictionSerializer,
)
from .tasks import run_detection_task


def _error(code: str, message: str, http_status: int = 400) -> Response:
    return Response({"error": {"code": code, "message": message, "details": {}}}, status=http_status)


class DetectionRunViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = DetectionRun.objects.select_related("model_version__model", "dataset", "created_by")
    serializer_class = DetectionRunSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["dataset", "model_version", "status"]
    required_permissions = {"list": "detection.read", "retrieve": "detection.read", "create": "detection.run",
                            "predictions": "detection.read"}  # fmt: skip

    def create(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        """Create a run (202) and score the dataset in a background worker."""
        ser = DetectionRunCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        dataset = Dataset.objects.filter(pk=v["dataset"]).first()
        if dataset is None:
            return _error("validation_error", "Unknown dataset.")
        try:
            run = services.create_run(version=v["model_version"], dataset=dataset, user=request.user,
                                      threshold=v.get("threshold"))  # fmt: skip
        except services.DetectionError as exc:
            return _error("detection_not_possible", str(exc))
        db_transaction.on_commit(lambda: run_detection_task.delay(run.pk))
        return Response(DetectionRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"], url_path="predictions")
    def predictions(self, request, pk=None):  # noqa: ANN001, ANN201
        """Scored transactions, highest score first. `?flagged=true` limits to alerts above the threshold."""
        run = self.get_object()
        qs = Prediction.objects.filter(run=run).select_related("transaction__sender", "transaction__receiver")
        flagged = request.query_params.get("flagged")
        if flagged in ("true", "false"):
            qs = qs.filter(flagged=flagged == "true")
        qs = qs.order_by("-score", "id")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(PredictionSerializer(page, many=True).data)


class TransactionPredictionsView(ListAPIView):
    """History of scores for one transaction across runs and model versions."""

    serializer_class = TransactionPredictionSerializer
    pagination_class = None
    required_permissions = {"GET": "detection.read"}

    def get_queryset(self):  # noqa: ANN201
        if getattr(self, "swagger_fake_view", False):  # schema generation has no URL kwargs
            return Prediction.objects.none()
        return (
            Prediction.objects.filter(transaction_id=self.kwargs["pk"], run__status="succeeded")
            .select_related("run__model_version__model")
            .order_by("-run__created_at", "-id")
        )
