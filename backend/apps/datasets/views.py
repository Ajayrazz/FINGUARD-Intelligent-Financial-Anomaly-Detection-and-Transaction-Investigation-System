import csv

from django.conf import settings
from django.http import StreamingHttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.audit import services as audit

from . import services
from .ingestion.mapping import PRESETS
from .models import ColumnMappingProfile, Dataset, ImportJob
from .serializers import (
    DatasetSerializer,
    ImportJobSerializer,
    ImportRowErrorSerializer,
    ImportUploadSerializer,
    MappingProfileSerializer,
    PreviewSerializer,
)


class DatasetViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    pagination_class = None  # a handful of datasets; the UI needs the full list for its selector
    required_permissions = {
        "list": "datasets.read",
        "retrieve": "datasets.read",
        "create": "datasets.create",
        "create_import": "imports.create",
        "preview_import": "imports.create",
    }

    def perform_create(self, serializer: DatasetSerializer) -> None:  # type: ignore[override]
        dataset = serializer.save(created_by=self.request.user)
        audit.log(
            "dataset.created", request=self.request, resource_type="dataset", resource_id=dataset.pk,
            changes={"name": dataset.name, "source_type": dataset.source_type},
        )  # fmt: skip

    @action(detail=True, methods=["post"], url_path="imports", parser_classes=[MultiPartParser, FormParser])
    def create_import(self, request, pk=None):  # noqa: ANN001, ANN201
        """Upload a CSV/XLSX. Returns 202 immediately; processing runs in a Celery worker."""
        dataset = self.get_object()
        ser = ImportUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        profile = v.get("mapping_profile")
        if profile is not None and profile.dataset_id != dataset.pk:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Mapping profile belongs to another dataset",
                        "details": {},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        job = services.create_file_import(
            dataset=dataset, user=request.user, request=request, uploaded=v["file"], raw_mapping=v.get("mapping"),
            preset=v.get("preset"), profile=profile, dup_policy=v["dup_policy"],
        )  # fmt: skip
        return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @action(
        detail=True,
        methods=["post"],
        url_path="imports/preview",
        parser_classes=[MultiPartParser, FormParser],
    )
    def preview_import(self, request, pk=None):  # noqa: ANN001, ANN201
        """Inspect a file's columns and first rows and suggest a mapping. Nothing is stored."""
        self.get_object()
        ser = PreviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = services.preview_upload(ser.validated_data["file"], settings.IMPORT_PREVIEW_ROWS)
        data["presets"] = sorted(PRESETS)
        return Response(data)


class ImportJobViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = ImportJob.objects.select_related("dataset", "created_by")
    serializer_class = ImportJobSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["dataset", "status", "source"]
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at", "-id"]
    required_permissions = {
        "list": "imports.read",
        "retrieve": "imports.read",
        "errors": "imports.read",
        "errors_export": "imports.read",
        "cancel": "imports.create",
        "resume": "imports.create",
    }

    @action(detail=True, methods=["get"])
    def errors(self, request, pk=None):  # noqa: ANN001, ANN201
        job = self.get_object()
        qs = job.row_errors.order_by("row_number")
        if code := request.query_params.get("error_code"):
            qs = qs.filter(error_code=code)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(ImportRowErrorSerializer(page, many=True).data)

    @action(detail=True, methods=["get"], url_path="errors/export")
    def errors_export(self, request, pk=None):  # noqa: ANN001, ANN201
        """Row errors as CSV. Cells that spreadsheets could interpret as formulas are neutralised."""
        job = self.get_object()

        def safe(v: object) -> str:
            s = str(v)
            return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s

        class Echo:
            def write(self, value: str) -> str:
                return value

        writer = csv.writer(Echo())

        def rows():  # noqa: ANN202
            yield writer.writerow(["row_number", "error_code", "message", "raw"])
            for e in job.row_errors.order_by("row_number").iterator(chunk_size=2000):
                yield writer.writerow([e.row_number, e.error_code, safe(e.message), safe(e.raw)])

        resp = StreamingHttpResponse(rows(), content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="import-{job.pk}-errors.csv"'
        return resp

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):  # noqa: ANN001, ANN201
        job = services.cancel_import(self.get_object(), user=request.user, request=request)
        return Response(ImportJobSerializer(job).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):  # noqa: ANN001, ANN201
        job = services.resume_import(
            self.get_object(), user=request.user, request=request, force=bool(request.data.get("force", False))
        )
        return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class MappingProfileViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = ColumnMappingProfile.objects.all()
    serializer_class = MappingProfileSerializer
    filterset_fields = ["dataset"]
    pagination_class = None
    required_permissions = {"list": "datasets.read", "retrieve": "datasets.read", "create": "datasets.create"}

    def perform_create(self, serializer: MappingProfileSerializer) -> None:  # type: ignore[override]
        serializer.save(created_by=self.request.user)
