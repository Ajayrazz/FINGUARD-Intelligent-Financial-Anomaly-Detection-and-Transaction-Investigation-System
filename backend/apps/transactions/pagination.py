from rest_framework.pagination import CursorPagination, PageNumberPagination


class _KeysetPagination(CursorPagination):
    ordering = ("-occurred_at", "-id")  # default; an `ordering=` query param is honoured via OrderingFilter
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class HybridPagination(PageNumberPagination):
    """Page-number pagination by default (UI page jumps, total count).

    Passing `?cursor=` (empty for the first page, then the opaque `next` value) switches to keyset
    pagination: constant-time at any depth and no COUNT(*), at the price of no random page access.
    Measured: OFFSET paging at page 20,000 of 1M rows takes ~830 ms; keyset stays flat (docs/06).
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def __init__(self) -> None:
        self._keyset: _KeysetPagination | None = None

    def paginate_queryset(self, queryset, request, view=None):  # noqa: ANN001, ANN201
        if "cursor" in request.query_params:
            self._keyset = _KeysetPagination()
            return self._keyset.paginate_queryset(queryset, request, view)
        self._keyset = None
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):  # noqa: ANN001, ANN201
        if self._keyset is not None:
            return self._keyset.get_paginated_response(data)
        return super().get_paginated_response(data)

    def get_paginated_response_schema(self, schema):  # noqa: ANN001, ANN201
        return super().get_paginated_response_schema(schema)
