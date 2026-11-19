from rest_framework.permissions import BasePermission


class HasRolePermission(BasePermission):
    """Default-deny RBAC check.

    A view must declare `required_permissions = {<action or HTTP method>: "resource.action"}`.
    A view or action without an entry is forbidden, so a forgotten declaration fails closed.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:  # noqa: ANN001
        required = getattr(view, "required_permissions", None)
        if not required:
            return False
        codename = required.get(getattr(view, "action", None) or request.method) or required.get(request.method)
        if codename is None:
            return False
        user = request.user
        return bool(user and user.is_authenticated and codename in user.permission_codenames)
