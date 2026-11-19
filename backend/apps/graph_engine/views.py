from datetime import UTC, datetime

from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.datasets.models import Dataset
from apps.transactions.models import Account, Transaction

from . import services
from .models import AccountGraphMetrics, GraphFinding, GraphSnapshot, Neo4jSyncState
from .serializers import (
    AccountMetricsSerializer,
    GraphFindingSerializer,
    GraphSnapshotCreateSerializer,
    GraphSnapshotSerializer,
)
from .tasks import build_snapshot_task, sync_neo4j_task


def _error(code: str, message: str, http_status: int = 400) -> Response:
    return Response({"error": {"code": code, "message": message, "details": {}}}, status=http_status)


class _Pager(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class GraphSnapshotViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = GraphSnapshot.objects.select_related("dataset", "created_by")
    serializer_class = GraphSnapshotSerializer
    required_permissions = {"list": "graph.read", "retrieve": "graph.read", "create": "graph.run"}

    def create(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        ser = GraphSnapshotCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        dataset = Dataset.objects.filter(pk=v["dataset"]).first()
        if dataset is None:
            return _error("validation_error", "Unknown dataset.")
        try:
            snap = services.create_snapshot(
                dataset=dataset, user=request.user, as_of=v.get("as_of"), window_days=v.get("window_days")
            )
        except services.GraphError as exc:
            return _error("graph_not_possible", str(exc))
        db_transaction.on_commit(lambda: build_snapshot_task.delay(snap.pk))
        return Response(GraphSnapshotSerializer(snap).data, status=status.HTTP_202_ACCEPTED)


class GraphFindingsView(APIView):
    """Findings of a snapshot (default: latest finished snapshot of `?dataset=`), highest score first."""

    required_permissions = {"GET": "graph.read"}

    def get(self, request):  # noqa: ANN001, ANN201
        q = request.query_params
        snap = None
        if "snapshot" in q:
            snap = GraphSnapshot.objects.filter(pk=q["snapshot"], status="succeeded").first()
        elif "dataset" in q:
            snap = (
                GraphSnapshot.objects.filter(dataset_id=q["dataset"], status="succeeded")
                .order_by("-created_at")
                .first()
            )
        else:
            return _error("validation_error", "Pass snapshot or dataset.")
        if snap is None:
            return _error("not_found", "No finished snapshot found.", 404)
        qs = GraphFinding.objects.filter(snapshot=snap)
        if q.get("type"):
            qs = qs.filter(finding_type=q["type"])
        if q.get("min_score"):
            try:
                qs = qs.filter(score__gte=float(q["min_score"]))
            except ValueError:
                return _error("validation_error", "min_score must be a number.")
        if q.get("account"):
            qs = qs.filter(account_ids__contains=[int(q["account"])]) if q["account"].isdigit() else qs
        pager = _Pager()
        page = pager.paginate_queryset(qs.order_by("-score", "id"), request)
        refs = dict(
            Account.objects.filter(pk__in={a for f in page for a in f.account_ids[:20]}).values_list(
                "pk", "account_ref"
            )
        )
        return pager.get_paginated_response(GraphFindingSerializer(page, many=True, context={"refs": refs}).data)


class AccountGraphMetricsView(APIView):
    required_permissions = {"GET": "graph.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        account = get_object_or_404(Account, pk=pk)
        q = request.query_params
        snaps = GraphSnapshot.objects.filter(dataset_id=account.dataset_id, status="succeeded")
        snap = snaps.filter(pk=q["snapshot"]).first() if "snapshot" in q else snaps.order_by("-created_at").first()
        if snap is None:
            return _error("not_found", "No finished graph snapshot for this account's dataset.", 404)
        m = AccountGraphMetrics.objects.filter(snapshot=snap, account=account).first()
        findings = GraphFinding.objects.filter(snapshot=snap, account_ids__contains=[account.pk]).order_by("-score")[
            :20
        ]
        return Response(
            {
                "snapshot": snap.pk,
                "account": account.pk,
                "account_ref": account.account_ref,
                "metrics": AccountMetricsSerializer(m).data if m else None,
                "note": None
                if m
                else "No stored metrics: fewer than 2 connections in this snapshot and in no finding.",
                "findings": GraphFindingSerializer(
                    findings, many=True, context={"refs": {account.pk: account.account_ref}}
                ).data,
            }
        )


def _neigh_params(request):  # noqa: ANN001, ANN202
    q = request.query_params
    try:
        depth, limit = int(q.get("depth", 1)), int(q.get("limit", 60))
        min_amount = float(q.get("min_amount", 0))
    except ValueError:
        return _error("validation_error", "depth, limit and min_amount must be numbers.")
    direction = q.get("direction", "both")
    if direction not in ("out", "in", "both"):
        return _error("validation_error", "direction must be out, in or both.")
    source = q.get("source", "auto")
    if source not in ("auto", "neo4j", "postgres"):
        return _error("validation_error", "source must be auto, neo4j or postgres.")
    bounds: list[float] = []
    for key, default in (("from", datetime(1970, 1, 1, tzinfo=UTC)), ("to", datetime(2100, 1, 1, tzinfo=UTC))):
        if key in q:
            from django.utils.dateparse import parse_datetime

            parsed = parse_datetime(q[key].replace(" ", "+"))
            if parsed is None:
                return _error("validation_error", f"{key} must be an ISO-8601 timestamp.")
            default = parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
        bounds.append(default.timestamp())
    return {
        "depth": depth,
        "limit": limit,
        "direction": direction,
        "min_amount": min_amount,
        "ts_from": bounds[0],
        "ts_to": bounds[1],
        "source": source,
    }


class AccountNeighborhoodView(APIView):
    """Nodes and aggregated edges around an account (hard caps: depth 3, 200 nodes, 500 edges)."""

    required_permissions = {"GET": "graph.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        params = _neigh_params(request)
        if isinstance(params, Response):
            return params
        account = get_object_or_404(Account, pk=pk)
        try:
            return Response(services.neighborhood(account, **params))
        except services.GraphError as exc:
            return _error("graph_not_possible", str(exc), 409)


class AccountTimelineView(APIView):
    """Transactions inside the account's neighborhood, newest first (cap 200)."""

    required_permissions = {"GET": "graph.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        params = _neigh_params(request)
        if isinstance(params, Response):
            return params
        account = get_object_or_404(Account, pk=pk)
        try:
            hood = services.neighborhood(account, **params)
        except services.GraphError as exc:
            return _error("graph_not_possible", str(exc), 409)
        ids = [n["id"] for n in hood["nodes"]]
        txs = (
            Transaction.objects.filter(dataset_id=account.dataset_id, sender_id__in=ids, receiver_id__in=ids)
            .select_related("sender", "receiver")
            .order_by("-occurred_at", "-id")[:200]
        )
        return Response(
            {
                "account": account.pk,
                "source": hood["source"],
                "truncated": hood["truncated"],
                "events": [
                    {
                        "transaction_id": t.pk,
                        "external_id": t.transaction_id,
                        "occurred_at": t.occurred_at,
                        "sender": t.sender.account_ref,
                        "receiver": t.receiver.account_ref if t.receiver else None,
                        "amount": str(t.amount),
                        "tx_type": t.tx_type,
                    }
                    for t in txs
                ],
            }
        )


class EdgeDetailView(APIView):
    """A graph edge is a transaction: details for the edge-click panel (no ground-truth label)."""

    required_permissions = {"GET": "graph.read"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        t = get_object_or_404(Transaction.objects.select_related("sender", "receiver"), pk=pk)
        return Response(
            {
                "transaction_id": t.pk,
                "external_id": t.transaction_id,
                "sender": {"id": t.sender_id, "account_ref": t.sender.account_ref},
                "receiver": {"id": t.receiver_id, "account_ref": t.receiver.account_ref} if t.receiver else None,
                "amount": str(t.amount),
                "currency": t.currency,
                "tx_type": t.tx_type,
                "occurred_at": t.occurred_at,
                "status": t.status,
            }
        )


class DatasetSyncView(APIView):
    """GET: projection status + drift check. POST: start a sync (`?rebuild=true` wipes and reloads)."""

    required_permissions = {"GET": "graph.read", "POST": "graph.run"}

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        dataset = get_object_or_404(Dataset, pk=pk)
        state = Neo4jSyncState.objects.filter(dataset=dataset).first()
        return Response(
            {
                "dataset": dataset.pk,
                "status": state.status if state else "never",
                "last_tx_id": state.last_tx_id if state else 0,
                "edges_synced": state.edges_synced if state else 0,
                "last_error": state.last_error if state else "",
                "updated_at": state.updated_at if state else None,
                "drift": services.drift_check(dataset.pk),
            }
        )

    def post(self, request, pk: int):  # noqa: ANN001, ANN201
        dataset = get_object_or_404(Dataset, pk=pk)
        rebuild = request.query_params.get("rebuild") == "true"
        state, _ = Neo4jSyncState.objects.get_or_create(dataset=dataset)
        if state.status == Neo4jSyncState.Status.RUNNING:
            return _error("sync_running", "A sync of this dataset is already running.", 409)
        from apps.audit import services as audit

        audit.log(
            "graph.sync.requested",
            actor=request.user,
            resource_type="dataset",
            resource_id=dataset.pk,
            changes={"rebuild": rebuild},
        )
        db_transaction.on_commit(lambda: sync_neo4j_task.delay(dataset.pk, rebuild))
        return Response(
            {"dataset": dataset.pk, "status": "queued", "rebuild": rebuild}, status=status.HTTP_202_ACCEPTED
        )
