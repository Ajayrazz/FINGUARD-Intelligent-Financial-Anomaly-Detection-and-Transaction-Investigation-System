import re
import uuid

_SAFE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIDMiddleware:
    """Attach a request id (client-supplied if well-formed) for log/audit correlation."""

    def __init__(self, get_response):  # noqa: ANN001
        self.get_response = get_response

    def __call__(self, request):  # noqa: ANN001
        supplied = request.META.get("HTTP_X_REQUEST_ID", "")
        request.request_id = supplied if _SAFE.match(supplied) else uuid.uuid4().hex
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response
