from django.contrib import admin

from .models import Permission, Role, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "full_name", "role", "is_active", "last_login"]
    list_filter = ["role", "is_active"]
    search_fields = ["email", "full_name"]
    exclude = ["password"]  # passwords are changed only through audited API/commands


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "label", "is_system"]


admin.site.register(Permission)
