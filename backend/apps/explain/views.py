from django.db import transaction as db_transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.model_registry.models import ModelVersion
from apps.transactions.models import Transaction

from . import services
from .models import Explanation, ExplanationJob
from .report import build_report
from .serializers import ExplanationJobSerializer, ExplanationSerializer, GenerateSerializer
from .tasks import generate_task


def _error(code: str, message: str, http_status: int = 400) -> Response:
    return Response({"error": {"code": code, "message": message, "details": {}}}, status=http_status)


def _latest_per_method(tx: Transaction) -> list[Explanation]:
    out: dict[str, Explanation] = {}
    for e in (
        Explanation.objects.filter(transaction=tx)
        .select_related("model_version__model", "prediction__run")
        .order_by("-generated_at", "-id")
    ):
        out.setdefault(e.method, e)
    return list(out.values())


class TransactionExplanationsView(APIView):
    """GET: the latest explanation of each kind (add `?all=true` for every stored one). POST: generate (202)."""

    required_permissions = {"GET": "explain.read", "POST": "explain.generate"}
    parser_classes = [JSONParser]

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        tx = get_object_or_404(Transaction, pk=pk)
        if request.query_params.get("all") == "true":
            rows = list(
                Explanation.objects.filter(transaction=tx)
                .select_related("model_version__model")
                .order_by("-generated_at", "-id")
            )
        else:
            rows = _latest_per_method(tx)
        return Response(ExplanationSerializer(rows, many=True, context={}).data)

    def post(self, request, pk: int):  # noqa: ANN001, ANN201
        tx = get_object_or_404(Transaction.objects.select_related("dataset"), pk=pk)
        ser = GenerateSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        mv = None
        if "model_version" in v:
            mv = ModelVersion.objects.filter(pk=v["model_version"]).first()
            if mv is None:
                return _error("validation_error", "Unknown model version.")
        try:
            job = services.create_job(tx=tx, user=request.user, methods=v.get("methods"), model_version=mv)
        except services.ExplanationError as exc:
            return _error("invalid_request", str(exc))
        db_transaction.on_commit(lambda: generate_task.delay(job.pk))
        return Response(ExplanationJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class ExplanationDetailView(APIView):
    required_permissions = {"GET": "explain.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        e = get_object_or_404(Explanation.objects.select_related("model_version__model", "transaction"), pk=pk)
        return Response(ExplanationSerializer(e, context={}).data)


class ExplanationJobView(APIView):
    required_permissions = {"GET": "explain.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        return Response(ExplanationJobSerializer(get_object_or_404(ExplanationJob, pk=pk)).data)


class TransactionExplanationReportView(APIView):
    required_permissions = {"GET": "explain.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        tx = get_object_or_404(Transaction.objects.select_related("dataset"), pk=pk)
        rows = _latest_per_method(tx)
        if not rows:
            return _error("not_found", "No explanations have been generated for this transaction.", 404)
        resp = HttpResponse(build_report(tx, rows), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="explanation-{tx.pk}.pdf"'
        return resp


class ModelVersionImportanceView(APIView):
    """GET: the latest stored global feature importance of a model version. POST: compute it (202)."""

    required_permissions = {"GET": "explain.read", "POST": "explain.generate"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        mv = get_object_or_404(ModelVersion, pk=pk)
        e = Explanation.objects.filter(model_version=mv, method="feature_importance").order_by("-generated_at").first()
        if e is None:
            return _error("not_found", "No global importance has been computed for this model version.", 404)
        return Response(ExplanationSerializer(e, context={}).data)

    def post(self, request, pk: int):  # noqa: ANN001, ANN201
        mv = get_object_or_404(ModelVersion, pk=pk)
        job = services.create_global_job(model_version=mv, user=request.user)
        db_transaction.on_commit(lambda: generate_task.delay(job.pk))
        return Response(ExplanationJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
