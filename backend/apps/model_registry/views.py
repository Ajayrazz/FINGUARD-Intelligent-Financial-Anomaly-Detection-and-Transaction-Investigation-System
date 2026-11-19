from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets

from .models import ModelVersion
from .serializers import ModelVersionDetailSerializer, ModelVersionSerializer


class ModelVersionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Registered model versions with their offline (research-data) evaluation. Read-only here."""

    queryset = (
        ModelVersion.objects.select_related("model")
        .prefetch_related("evaluations")
        .order_by("model__name", "-trained_at")
    )
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "model__task_type", "model__algorithm"]
    pagination_class = None  # a few dozen versions; the UI compares them side by side
    required_permissions = {"list": "models.read", "retrieve": "models.read"}

    def get_serializer_class(self):  # noqa: ANN201
        return ModelVersionDetailSerializer if self.action == "retrieve" else ModelVersionSerializer
