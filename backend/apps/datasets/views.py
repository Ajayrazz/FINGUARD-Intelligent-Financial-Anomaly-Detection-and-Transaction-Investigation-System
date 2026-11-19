from rest_framework import mixins, viewsets

from apps.audit import services as audit

from .models import Dataset
from .serializers import DatasetSerializer


class DatasetViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    pagination_class = None  # a handful of datasets; the UI needs the full list for its selector
    required_permissions = {"list": "datasets.read", "retrieve": "datasets.read", "create": "datasets.create"}

    def perform_create(self, serializer: DatasetSerializer) -> None:  # type: ignore[override]
        dataset = serializer.save(created_by=self.request.user)
        audit.log(
            "dataset.created", request=self.request, resource_type="dataset", resource_id=dataset.pk,
            changes={"name": dataset.name, "source_type": dataset.source_type},
        )  # fmt: skip
