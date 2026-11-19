import django_filters
from rest_framework import viewsets

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogFilter(django_filters.FilterSet):
    actor_email = django_filters.CharFilter(lookup_expr="icontains")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["action", "resource_type", "resource_id", "actor_email", "created_after", "created_before"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    required_permissions = {"list": "audit.read", "retrieve": "audit.read"}
    filterset_class = AuditLogFilter
