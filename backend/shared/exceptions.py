from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Uniform error envelope: {"error": {"code", "message", "details"}} (docs/07)."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    details = data if isinstance(data, dict) and "detail" not in data else {}
    message = str(data["detail"]) if isinstance(data, dict) and "detail" in data else "Request failed"
    codes = exc.get_codes() if hasattr(exc, "get_codes") else None
    code = codes if isinstance(codes, str) else getattr(exc, "default_code", "error")
    if response.status_code == 400:
        message = "Validation failed"
        details = data if isinstance(data, dict) else {"non_field_errors": data}
        code = "validation_error"
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
