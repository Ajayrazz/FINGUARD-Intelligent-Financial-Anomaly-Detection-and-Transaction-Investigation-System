from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "actor_email", "resource_type", "resource_id"]
    list_filter = ["action", "resource_type"]

    def has_add_permission(self, request, obj=None):  # noqa: ANN001, ANN201
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001, ANN201
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ANN001, ANN201
        return False
