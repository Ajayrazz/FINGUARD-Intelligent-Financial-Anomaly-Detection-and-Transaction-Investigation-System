from django.db import transaction as db_transaction
from django.http import FileResponse, HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.datasets.models import Dataset

from . import services
from .models import DuplicateCandidate, DuplicateScanRun, Invoice, InvoiceDocument
from .report import build_report
from .serializers import (
    CandidateDetailSerializer,
    CandidateSerializer,
    InvoiceFieldsSerializer,
    InvoiceSerializer,
    ReviewSerializer,
    ScanCreateSerializer,
    ScanRunSerializer,
)
from .tasks import process_invoice_task, run_scan_task


def _error(code: str, message: str, http_status: int = 400) -> Response:
    return Response({"error": {"code": code, "message": message, "details": {}}}, status=http_status)


class InvoiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Invoice.objects.select_related("document", "verified_by").order_by("-id")
    serializer_class = InvoiceSerializer
    required_permissions = {"list": "duplicates.read", "retrieve": "duplicates.read", "upload": "duplicates.create",
                            "fields": "duplicates.review", "file": "duplicates.read"}  # fmt: skip

    @action(detail=False, methods=["post"], url_path="upload", parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):  # noqa: ANN001, ANN201
        """Upload a PNG/JPEG/PDF invoice (field `file`). Returns 202; OCR and matching run in a worker."""
        f = request.FILES.get("file")
        if f is None:
            return _error("validation_error", "No file was uploaded (field name: file).")
        try:
            doc = services.store_invoice_upload(f, request.user)
        except services.DuplicateError as exc:
            return _error("invalid_file", str(exc))
        inv = Invoice.objects.create(document=doc)  # empty until OCR finishes
        db_transaction.on_commit(lambda: process_invoice_task.delay(doc.pk))
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["patch"], url_path="fields", parser_classes=[JSONParser])
    def fields(self, request, pk=None):  # noqa: ANN001, ANN201
        """Human correction of OCR-extracted fields. Marks the invoice verified by this user."""
        inv = self.get_object()
        ser = InvoiceFieldsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        inv = services.correct_invoice_fields(inv, user=request.user, values=dict(ser.validated_data))
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["get"], url_path="file")
    def file(self, request, pk=None):  # noqa: ANN001, ANN201
        """The stored invoice image/PDF, for review. Authenticated; served with a server-chosen name and nosniff."""
        inv = self.get_object()
        if inv.document is None:
            return _error("not_found", "No file for this invoice.", 404)
        doc: InvoiceDocument = inv.document
        resp = FileResponse(open(doc.file_path, "rb"), content_type=doc.mime)  # noqa: SIM115 - FileResponse closes it
        ext = {"image/png": "png", "image/jpeg": "jpg", "application/pdf": "pdf"}[doc.mime]
        resp["Content-Disposition"] = f'inline; filename="invoice-{inv.pk}.{ext}"'
        resp["X-Content-Type-Options"] = "nosniff"
        return resp


class ScanView(APIView):
    """Start a duplicate scan (transactions of a dataset / all invoices). Returns 202."""

    required_permissions = {"POST": "duplicates.run"}

    def post(self, request):  # noqa: ANN001, ANN201
        ser = ScanCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        dataset = None
        if v["kind"] == "transaction" and "dataset" in v:
            dataset = Dataset.objects.filter(pk=v["dataset"]).first()
            if dataset is None:
                return _error("validation_error", "Unknown dataset.")
        run = DuplicateScanRun.objects.create(kind=v["kind"], dataset=dataset, created_by=request.user)
        from apps.audit import services as audit

        audit.log("duplicates.scan.created", actor=request.user, resource_type="duplicate_scan", resource_id=run.pk,
                  changes={"kind": v["kind"], "dataset": dataset.pk if dataset else None})  # fmt: skip
        db_transaction.on_commit(lambda: run_scan_task.delay(run.pk))
        return Response(ScanRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


class ScanListView(ListAPIView):
    queryset = DuplicateScanRun.objects.select_related("dataset")
    serializer_class = ScanRunSerializer
    required_permissions = {"GET": "duplicates.read"}


class CandidateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = DuplicateCandidate.objects.select_related("reviewed_by")
    required_permissions = {"list": "duplicates.read", "retrieve": "duplicates.read", "review": "duplicates.review",
                            "report": "duplicates.read"}  # fmt: skip

    def get_serializer_class(self):  # noqa: ANN201
        return CandidateDetailSerializer if self.action == "retrieve" else CandidateSerializer

    def get_queryset(self):  # noqa: ANN201
        qs = super().get_queryset()
        q = self.request.query_params
        for key, field in (("kind", "kind"), ("match_class", "match_class"), ("review_status", "review_status")):
            if q.get(key):
                qs = qs.filter(**{field: q[key]})
        if q.get("min_score"):
            try:
                qs = qs.filter(similarity_score__gte=float(q["min_score"]))
            except ValueError:
                pass
        return qs.order_by("-similarity_score", "id")

    @action(detail=True, methods=["post"], url_path="review", parser_classes=[JSONParser])
    def review(self, request, pk=None):  # noqa: ANN001, ANN201
        """Record the human decision. Nothing is 'confirmed' unless a reviewer says so here."""
        cand = self.get_object()
        ser = ReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cand = services.review_candidate(
            cand, user=request.user, decision=ser.validated_data["decision"], notes=ser.validated_data["notes"]
        )
        return Response(CandidateDetailSerializer(cand).data)

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, pk=None):  # noqa: ANN001, ANN201
        cand = self.get_object()
        resp = HttpResponse(build_report(cand), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="duplicate-candidate-{cand.pk}.pdf"'
        return resp
