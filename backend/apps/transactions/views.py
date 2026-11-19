from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from . import services
from .filters import AccountFilter, TransactionFilter
from .models import Account, Transaction
from .pagination import HybridPagination
from .serializers import (
    AccountDetailSerializer,
    AccountSerializer,
    StatusUpdateSerializer,
    TransactionDetailSerializer,
    TransactionEventSerializer,
    TransactionListSerializer,
)

RELATED_LIMIT = 50


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.select_related("dataset", "sender", "receiver")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TransactionFilter
    pagination_class = HybridPagination
    ordering_fields = ["occurred_at", "amount", "id"]
    ordering = ["-occurred_at", "-id"]
    required_permissions = {
        "list": "transactions.read",
        "retrieve": "transactions.read",
        "events": "transactions.read",
        "related": "transactions.read",
        "update_status": "transactions.update_status",
    }

    def get_serializer_class(self):  # noqa: ANN201
        if self.action == "list":
            return TransactionListSerializer
        if self.action == "update_status":
            return StatusUpdateSerializer
        return TransactionDetailSerializer

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):  # noqa: ANN001, ANN201
        tx = self.get_object()
        ser = StatusUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tx = services.change_status(
            tx_id=tx.pk,
            new_status=ser.validated_data["status"],
            reason=ser.validated_data.get("reason", ""),
            actor=request.user,
            request=request,
        )
        tx = self.get_queryset().get(pk=tx.pk)
        return Response(TransactionDetailSerializer(tx).data)

    @action(detail=True, methods=["get"], pagination_class=None)
    def events(self, request, pk=None):  # noqa: ANN001, ANN201
        tx = self.get_object()
        return Response(TransactionEventSerializer(tx.events.select_related("actor"), many=True).data)

    @action(detail=True, methods=["get"], pagination_class=None)
    def related(self, request, pk=None):  # noqa: ANN001, ANN201
        """Other transactions between the same two accounts (either direction) in the same dataset."""
        tx = self.get_object()
        if tx.receiver_id is None:
            return Response([])
        pair = Q(sender_id=tx.sender_id, receiver_id=tx.receiver_id) | Q(
            sender_id=tx.receiver_id, receiver_id=tx.sender_id
        )
        qs = (
            self.get_queryset()
            .filter(pair, dataset_id=tx.dataset_id)
            .exclude(pk=tx.pk)
            .order_by("-occurred_at", "-id")[:RELATED_LIMIT]
        )
        return Response(TransactionListSerializer(qs, many=True).data)


class AccountViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Account.objects.select_related("dataset")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = AccountFilter
    ordering_fields = ["account_ref", "last_seen_at"]
    ordering = ["account_ref"]
    required_permissions = {
        "list": "accounts.read",
        "retrieve": "accounts.read",
        "transactions": "transactions.read",
    }

    def get_serializer_class(self):  # noqa: ANN201
        return AccountDetailSerializer if self.action == "retrieve" else AccountSerializer

    def get_queryset(self):  # noqa: ANN201
        qs = super().get_queryset()
        if self.action == "retrieve":
            money = DecimalField(max_digits=22, decimal_places=2)
            qs = qs.annotate(
                sent_count=Count("sent_transactions", distinct=True),
                sent_total=Coalesce(Sum("sent_transactions__amount"), 0, output_field=money),
            )
            # Received aggregates computed separately: one join per aggregate avoids row multiplication.
        return qs

    def retrieve(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        account = self.get_object()
        received = account.received_transactions.aggregate(
            n=Count("id"),
            total=Coalesce(Sum("amount"), 0, output_field=DecimalField(max_digits=22, decimal_places=2)),
        )
        account.received_count = received["n"]
        account.received_total = received["total"]
        return Response(AccountDetailSerializer(account).data)

    @action(detail=True, methods=["get"])
    def transactions(self, request, pk=None):  # noqa: ANN001, ANN201
        """Transactions of this account. direction=out (sent), in (received) or both (default)."""
        account = self.get_object()
        direction = request.query_params.get("direction", "both")
        if direction not in {"in", "out", "both"}:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "direction must be in, out or both",
                        "details": {},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        cond = {"in": Q(receiver=account), "out": Q(sender=account)}.get(
            direction, Q(sender=account) | Q(receiver=account)
        )
        qs = (
            Transaction.objects.select_related("dataset", "sender", "receiver")
            .filter(cond)
            .order_by("-occurred_at", "-id")
        )
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(TransactionListSerializer(page, many=True).data)
