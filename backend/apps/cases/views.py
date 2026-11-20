from django.db.models import Case as DbCase
from django.db.models import Count, IntegerField, Q, Value, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alerts.models import Alert
from apps.datasets.models import Dataset
from apps.transactions.models import Transaction

from . import services
from .models import Case, CaseNote
from .report import build_report
from .serializers import (
    AddTransactionSerializer,
    AssignSerializer,
    CaseCreateSerializer,
    CaseDetailSerializer,
    CaseSerializer,
    CaseTransactionSerializer,
    CaseUpdateSerializer,
    CloseSerializer,
    EventSerializer,
    EvidenceSerializer,
    LinkAlertSerializer,
    LinkCaseSerializer,
    NoteBodySerializer,
    NoteEditSerializer,
    NoteSerializer,
    ReasonSerializer,
    ResolveSerializer,
    TransitionSerializer,
)


def _error(code: str, message: str, http_status: int = 400) -> Response:
    return Response({"error": {"code": code, "message": message, "details": {}}}, status=http_status)


def _run(fn, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
    try:
        return fn(*args, **kwargs), None
    except services.CaseError as exc:
        return None, _error(
            {403: "permission_denied", 409: "invalid_transition"}.get(exc.status, "validation_error"),
            str(exc),
            exc.status,
        )


PRIORITY_ORDER = DbCase(
    When(priority="critical", then=Value(3)),
    When(priority="high", then=Value(2)),
    When(priority="medium", then=Value(1)),
    default=Value(0),
    output_field=IntegerField(),
)


class CaseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = Case.objects.select_related("assignee", "created_by", "resolved_by", "closed_by")
    required_permissions = {
        "list": "cases.read", "retrieve": "cases.read", "create": "cases.create", "partial_update": "cases.update", "transition": "cases.transition",
        "assign": "cases.assign", "escalate": "cases.escalate", "resolve": "cases.resolve", "close": "cases.close", "events": "cases.read",
        "accounts": "cases.read", "report": "cases.read", "summary": "cases.summary", "assignees": "cases.assign",
    }  # fmt: skip

    def get_serializer_class(self):  # noqa: ANN201
        return CaseDetailSerializer if self.action in ("retrieve", "partial_update") else CaseSerializer

    def get_queryset(self):  # noqa: ANN201
        qs = super().get_queryset()
        q = self.request.query_params
        for key in ("status", "priority", "outcome", "dataset"):
            if q.get(key):
                qs = qs.filter(**{key: q[key]})
        if q.get("open") == "true":
            qs = qs.exclude(status="closed")
        if q.get("assignee") == "me":
            qs = qs.filter(assignee=self.request.user)
        elif q.get("assignee") == "none":
            qs = qs.filter(assignee__isnull=True)
        elif q.get("assignee"):
            qs = qs.filter(assignee_id=q["assignee"])
        if q.get("search"):
            term = q["search"].strip()
            qs = qs.filter(
                Q(case_ref__iexact=term)
                | Q(case_ref__istartswith=term)
                | Q(title__icontains=term)
                | Q(case_alerts__alert__account__account_ref__iexact=term)
            ).distinct()
        for key, field in (("opened_after", "opened_at__gte"), ("opened_before", "opened_at__lte")):
            if q.get(key):
                qs = qs.filter(**{field: q[key].replace(" ", "+")})
        # prioritisation: open before closed, then priority, then newest
        if self.action == "list":
            qs = qs.annotate(_alert_count=Count("case_alerts", distinct=True), _transaction_count=Count("case_transactions", distinct=True))
        return qs.annotate(
            _prio=PRIORITY_ORDER,
            _open=DbCase(When(status="closed", then=Value(0)), default=Value(1), output_field=IntegerField()),
        ).order_by("-_open", "-_prio", "-opened_at", "-id")

    def create(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        ser = CaseCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        alert = None
        if "alert" in v:
            alert = Alert.objects.filter(pk=v["alert"]).first()
            if alert is None:
                return _error("validation_error", "Unknown alert.")
        dataset = (
            Dataset.objects.filter(pk=v["dataset"]).first() if "dataset" in v else (alert.dataset if alert else None)
        )
        case, err = _run(
            services.create_case,
            user=request.user,
            title=v["title"],
            description=v["description"],
            priority=v["priority"],
            dataset=dataset,
            alert=alert,
        )
        if err:
            return err
        for tid in v.get("transactions", [])[:200]:
            tx = Transaction.objects.filter(pk=tid).first()
            if tx:
                services.add_transaction(case, tx, request.user)
        return Response(CaseDetailSerializer(case, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        ser = CaseUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        case, err = _run(services.update_fields, self.get_object(), request.user, dict(ser.validated_data))
        return err or Response(CaseDetailSerializer(case, context={"request": request}).data)

    def _go(self, request, to_status: str, **kw):  # noqa: ANN001, ANN003, ANN202
        case, err = _run(services.transition, self.get_object(), request.user, to_status, **kw)
        return err or Response(CaseDetailSerializer(case, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="transition", parser_classes=[JSONParser])
    def transition(self, request, pk=None):  # noqa: ANN001, ANN201
        ser = TransitionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        return self._go(request, v["to_status"], reason=v["reason"], outcome=v["outcome"], summary=v["summary"])

    @action(detail=True, methods=["post"], url_path="escalate", parser_classes=[JSONParser])
    def escalate(self, request, pk=None):  # noqa: ANN001, ANN201
        ser = ReasonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return self._go(request, "escalated", reason=ser.validated_data["reason"])

    @action(detail=True, methods=["post"], url_path="resolve", parser_classes=[JSONParser])
    def resolve(self, request, pk=None):  # noqa: ANN001, ANN201
        ser = ResolveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        return self._go(request, "resolved", outcome=v["outcome"], summary=v["summary"], reason=v["reason"])

    @action(detail=True, methods=["post"], url_path="close", parser_classes=[JSONParser])
    def close(self, request, pk=None):  # noqa: ANN001, ANN201
        ser = CloseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return self._go(request, "closed", reason=ser.validated_data["reason"])

    @action(detail=True, methods=["post"], url_path="assign", parser_classes=[JSONParser])
    def assign(self, request, pk=None):  # noqa: ANN001, ANN201
        ser = AssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        assignee = services.eligible_assignees().filter(pk=ser.validated_data["assignee"]).first()
        if assignee is None:
            return _error("validation_error", "That user cannot work on cases.")
        case, err = _run(services.assign, self.get_object(), request.user, assignee)
        return err or Response(CaseDetailSerializer(case, context={"request": request}).data)

    @action(detail=True, methods=["get"], url_path="events", pagination_class=None)
    def events(self, request, pk=None):  # noqa: ANN001, ANN201
        """The immutable history (the timeline). Closed cases keep theirs viewable."""
        return Response(EventSerializer(self.get_object().events.select_related("actor"), many=True).data)

    @action(detail=True, methods=["get"], url_path="accounts", pagination_class=None)
    def accounts(self, request, pk=None):  # noqa: ANN001, ANN201
        return Response(services.involved_accounts(self.get_object()))

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, pk=None):  # noqa: ANN001, ANN201
        case = self.get_object()
        resp = HttpResponse(build_report(case), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="case-{case.case_ref}.pdf"'
        return resp

    @action(detail=False, methods=["get"], url_path="summary", pagination_class=None)
    def summary(self, request):  # noqa: ANN001, ANN201
        by_status = {r["status"]: r["n"] for r in Case.objects.values("status").annotate(n=Count("id"))}
        open_prio = {
            r["priority"]: r["n"]
            for r in Case.objects.exclude(status="closed").values("priority").annotate(n=Count("id"))
        }
        outcomes = {
            r["outcome"]: r["n"] for r in Case.objects.exclude(outcome="").values("outcome").annotate(n=Count("id"))
        }
        return Response({"by_status": by_status, "open_by_priority": {p: open_prio.get(p, 0) for p in ("critical", "high", "medium", "low")}, "outcomes": outcomes,
                         "unassigned_open": Case.objects.exclude(status="closed").filter(assignee__isnull=True).count()})  # fmt: skip

    @action(detail=False, methods=["get"], url_path="assignees", pagination_class=None)
    def assignees(self, request):  # noqa: ANN001, ANN201
        return Response(
            [{"id": u.pk, "email": u.email, "full_name": u.full_name} for u in services.eligible_assignees()]
        )


class CaseNotesView(APIView):
    required_permissions = {"GET": "cases.read", "POST": "cases.comment"}
    parser_classes = [JSONParser]

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        case = get_object_or_404(Case, pk=pk)
        return Response(NoteSerializer(case.notes.select_related("author"), many=True).data)

    def post(self, request, pk: int):  # noqa: ANN001, ANN201
        case = get_object_or_404(Case, pk=pk)
        ser = NoteBodySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        note, err = _run(services.add_note, case, request.user, ser.validated_data["kind"], ser.validated_data["body"])
        return err or Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)


class CaseNoteDetailView(APIView):
    required_permissions = {"PATCH": "cases.comment", "GET": "cases.read"}
    parser_classes = [JSONParser]

    def patch(self, request, pk: int, note_id: int):  # noqa: ANN001, ANN201
        note = get_object_or_404(CaseNote.objects.select_related("case"), pk=note_id, case_id=pk)
        ser = NoteEditSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        _, err = _run(services.edit_note, note, request.user, ser.validated_data["body"])
        return err or Response(NoteSerializer(note).data)

    def get(self, request, pk: int, note_id: int):  # noqa: ANN001, ANN201
        """Every revision, oldest first: earlier text is never lost."""
        note = get_object_or_404(CaseNote, pk=note_id, case_id=pk)
        return Response(
            [
                {"revision": r.revision, "body": r.body, "edited_by": r.edited_by.email, "created_at": r.created_at}
                for r in note.revisions.select_related("edited_by")
            ]
        )


class CaseEvidenceView(APIView):
    required_permissions = {"GET": "cases.read", "POST": "cases.evidence"}
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        return Response(
            EvidenceSerializer(get_object_or_404(Case, pk=pk).evidence.select_related("uploaded_by"), many=True).data
        )

    def post(self, request, pk: int):  # noqa: ANN001, ANN201
        case = get_object_or_404(Case, pk=pk)
        f = request.FILES.get("file")
        if f is None:
            return _error("validation_error", "No file was uploaded (field name: file).")
        ev, err = _run(services.add_evidence, case, request.user, f, str(request.data.get("description", "")))
        return err or Response(EvidenceSerializer(ev).data, status=status.HTTP_201_CREATED)


class CaseEvidenceDownloadView(APIView):
    required_permissions = {"GET": "cases.evidence"}

    def get(self, request, pk: int, evidence_id: int):  # noqa: ANN001, ANN201
        from .models import CaseEvidence

        ev = get_object_or_404(
            CaseEvidence, pk=evidence_id, case_id=pk
        )  # the case id in the URL must match: no cross-case access by guessing ids
        data, err = _run(services.read_evidence, ev, request.user)
        if err:
            return err
        resp = HttpResponse(data, content_type=ev.mime)
        ext = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg", "text/plain": "txt"}[ev.mime]
        resp["Content-Disposition"] = f'attachment; filename="evidence-{ev.pk}.{ext}"'
        resp["X-Content-Type-Options"] = "nosniff"
        return resp


class CaseAlertsView(APIView):
    required_permissions = {"GET": "cases.read", "POST": "cases.update"}
    parser_classes = [JSONParser]

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        from apps.alerts.serializers import AlertSerializer

        case = get_object_or_404(Case, pk=pk)
        return Response(
            AlertSerializer(
                [
                    link.alert
                    for link in case.case_alerts.select_related(
                        "alert__transaction", "alert__account", "alert__assignee", "alert__assessment", "alert__dataset"
                    )
                ],
                many=True,
            ).data
        )

    def post(self, request, pk: int):  # noqa: ANN001, ANN201
        case = get_object_or_404(Case, pk=pk)
        ser = LinkAlertSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        alert = Alert.objects.filter(pk=ser.validated_data["alert"]).first()
        if alert is None:
            return _error("validation_error", "Unknown alert.")
        _, err = _run(services.link_alert, case, alert, request.user)
        return err or Response(
            CaseDetailSerializer(case, context={"request": request}).data, status=status.HTTP_201_CREATED
        )


class CaseTransactionsView(APIView):
    required_permissions = {"GET": "cases.read", "POST": "cases.update"}
    parser_classes = [JSONParser]

    def get(self, request, pk: int):  # noqa: ANN001, ANN201
        case = get_object_or_404(Case, pk=pk)
        return Response(
            CaseTransactionSerializer(
                case.case_transactions.select_related("transaction__sender", "transaction__receiver").order_by(
                    "transaction__occurred_at"
                ),
                many=True,
            ).data
        )

    def post(self, request, pk: int):  # noqa: ANN001, ANN201
        case = get_object_or_404(Case, pk=pk)
        ser = AddTransactionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tx = Transaction.objects.filter(pk=ser.validated_data["transaction"]).first()
        if tx is None:
            return _error("validation_error", "Unknown transaction.")
        link, err = _run(services.add_transaction, case, tx, request.user, ser.validated_data["note"])
        return err or Response(CaseTransactionSerializer(link).data, status=status.HTTP_201_CREATED)


class AlertCreateCaseView(APIView):
    """Open a case from an alert (the alert's transaction is attached; the alert is acknowledged)."""

    required_permissions = {"POST": "cases.create"}
    parser_classes = [JSONParser]

    def post(self, request, pk: int):  # noqa: ANN001, ANN201
        alert = get_object_or_404(Alert, pk=pk)
        if alert.case_links.exclude(case__status="closed").exists():
            return _error("already_linked", "This alert is already part of an open case.", 409)
        ser = CaseCreateSerializer(
            data={
                "title": f"{alert.alert_type.replace('_', ' ').capitalize()}: {alert.reason[:120]}",
                "description": alert.reason,
                "priority": alert.severity,
                **request.data,
            }
        )
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        case, err = _run(
            services.create_case,
            user=request.user,
            title=v["title"],
            description=v["description"],
            priority=v["priority"],
            dataset=alert.dataset,
            alert=alert,
        )
        return err or Response(
            CaseDetailSerializer(case, context={"request": request}).data, status=status.HTTP_201_CREATED
        )


class AlertLinkCaseView(APIView):
    required_permissions = {"POST": "cases.update"}
    parser_classes = [JSONParser]

    def post(self, request, pk: int):  # noqa: ANN001, ANN201
        alert = get_object_or_404(Alert, pk=pk)
        ser = LinkCaseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        case = Case.objects.filter(pk=ser.validated_data["case"]).first()
        if case is None:
            return _error("validation_error", "Unknown case.")
        _, err = _run(services.link_alert, case, alert, request.user)
        return err or Response(
            CaseDetailSerializer(case, context={"request": request}).data, status=status.HTTP_201_CREATED
        )
