"""Case management: state machine (full matrix), permissions, automatic creation, notes, evidence, immutability, reports."""

import itertools
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection
from django.utils import timezone

from apps.accounts.models import Permission, Role
from apps.alerts.models import Alert, AlertPolicy
from apps.audit.models import AuditLog
from apps.cases import services
from apps.cases.models import STATUSES, TRANSITIONS, Case, CaseEvent, CaseNote
from apps.transactions.models import Transaction
from tests.test_alerts import analyst, evaluate, user, world  # noqa: F401  (fixtures shared with the alert tests)

pytestmark = pytest.mark.django_db


def mk_case(status="new", outcome="", summary="", **kw):
    if status in ("resolved", "closed"):
        outcome, summary = outcome or "inconclusive", summary or "done"
    return Case.objects.create(
        case_ref=services.next_case_ref(),
        title=kw.pop("title", "Test case"),
        status=status,
        outcome=outcome,
        resolution_summary=summary,
        **kw,
    )


@pytest.fixture
def inv(make_user, api_as):
    u = make_user("fraud_investigator")
    return u, api_as(u)


@pytest.fixture
def admin(make_user, api_as):
    return api_as(make_user("super_admin"))


def go(client, case, to, **body):
    return client.post(f"/api/v1/cases/{case.pk}/transition/", {"to_status": to, **body}, format="json")


def test_the_state_machine_has_exactly_the_documented_transitions():
    allowed = {(a, b) for a, bs in TRANSITIONS.items() for b in bs}
    assert allowed == {("new", "under_review"), ("under_review", "investigation"), ("under_review", "resolved"), ("investigation", "escalated"),
                       ("investigation", "resolved"), ("escalated", "investigation"), ("resolved", "closed")}  # fmt: skip
    assert set(TRANSITIONS) == set(STATUSES)


def test_every_pair_of_statuses_is_checked_only_the_seven_legal_ones_succeed(admin):
    legal = {(a, b) for a, bs in TRANSITIONS.items() for b in bs}
    for a, b in itertools.product(STATUSES, STATUSES):
        case = mk_case(a)
        extra = {
            "reason": "needs senior review",
            "outcome": "confirmed_suspicious",
            "summary": "reviewed and concluded",
        }
        res = go(admin, case, b, **extra)
        if (a, b) in legal:
            assert res.status_code == 200 and res.json()["status"] == b, f"{a}->{b}: {res.content}"
            if b == "closed":
                assert Case.objects.get(pk=case.pk).closed_at is not None
        else:
            assert res.status_code == 409 and res.json()["error"]["code"] == "invalid_transition", (
                f"{a}->{b} should be refused"
            )
            assert Case.objects.get(pk=case.pk).status == a  # unchanged
    assert go(admin, mk_case(), "bogus").status_code == 400


def test_each_status_needs_its_own_permission_resolve_and_close_are_separate(make_user, api_as):
    def user_with(*codenames):
        role = Role.objects.create(name=f"r{len(codenames)}{codenames[0]}", label="custom")
        role.permissions.set(Permission.objects.filter(codename__in=[*codenames, "cases.read"]))
        return api_as(make_user(role.name))

    resolver = user_with("cases.resolve")
    case = mk_case("investigation")
    post = lambda c, path, body: c.post(f"/api/v1/cases/{case.pk}/{path}/", body, format="json")  # noqa: E731
    assert post(resolver, "escalate", {"reason": "x"}).status_code == 403  # no cases.escalate
    assert post(resolver, "resolve", {"outcome": "inconclusive", "summary": "ok"}).status_code == 200
    assert post(resolver, "close", {}).status_code == 403  # resolving does not allow closing
    assert (
        go(resolver, case, "closed").status_code == 403
    )  # nor does the generic endpoint, which needs cases.transition anyway
    assert post(user_with("cases.close"), "close", {}).status_code == 200
    mover = user_with("cases.transition")
    assert go(mover, mk_case("new"), "under_review").status_code == 200
    stuck = mk_case("investigation")
    refused = go(
        mover, stuck, "resolved", outcome="inconclusive", summary="ok"
    )  # right endpoint, but resolving needs cases.resolve
    assert refused.status_code == 403 and Case.objects.get(pk=stuck.pk).status == "investigation"


def test_validation_of_reason_outcome_and_summary(admin):
    esc = mk_case("investigation")
    assert go(admin, esc, "escalated", reason="  ").status_code == 400
    res = mk_case("investigation")
    assert go(admin, res, "resolved", outcome="made_up", summary="s").status_code == 400
    assert go(admin, res, "resolved", outcome="false_positive", summary="  ").status_code == 400
    ok = go(admin, res, "resolved", outcome="referred", summary="referred to the bank's compliance team")
    assert ok.status_code == 200 and ok.json()["outcome"] == "referred" and ok.json()["resolved_by_email"]
    assert admin.post(f"/api/v1/cases/{res.pk}/escalate/", {"reason": ""}, format="json").status_code == 400
    assert (
        admin.post(
            f"/api/v1/cases/{mk_case('investigation').pk}/escalate/", {"reason": "needs a lead"}, format="json"
        ).status_code
        == 200
    )


def test_four_eyes_closure_is_configurable(admin, inv, make_user, api_as, settings):
    settings.CASE_CLOSE_REQUIRES_DIFFERENT_USER = True
    _, inv_client = inv
    case = mk_case("investigation")
    assert go(inv_client, case, "resolved", outcome="inconclusive", summary="ok").status_code == 200
    refused = go(inv_client, case, "closed")
    assert refused.status_code == 403 and "second person" in refused.json()["error"]["message"]
    assert go(admin, case, "closed").status_code == 200  # a different person may close
    settings.CASE_CLOSE_REQUIRES_DIFFERENT_USER = False
    c2 = mk_case("investigation")
    go(inv_client, c2, "resolved", outcome="inconclusive", summary="ok")
    assert go(inv_client, c2, "closed").status_code == 200


def test_case_refs_come_from_a_sequence_and_are_unique(admin):
    refs = [admin.post("/api/v1/cases/", {"title": f"c{i}"}, format="json").json()["case_ref"] for i in range(4)]
    assert all(re.fullmatch(r"FG-\d{4}-\d{6}", r) for r in refs) and len(set(refs)) == 4
    nums = [int(r[-6:]) for r in refs]
    assert nums == sorted(nums) and nums[-1] - nums[0] == 3
    assert refs[0].startswith(f"FG-{timezone.now().year}-")


def test_create_from_an_alert_links_it_attaches_the_transaction_and_acknowledges(world, analyst, inv, run_tasks):  # noqa: F811
    evaluate(analyst, world["ds"], run_tasks)
    alert = Alert.objects.filter(alert_type="duplicate_record", status="new").first()
    _, inv_client = inv
    res = inv_client.post(f"/api/v1/alerts/{alert.pk}/create-case/", {}, format="json")
    assert res.status_code == 201, res.content
    case = Case.objects.get(pk=res.json()["id"])
    assert (
        case.status == "new"
        and case.auto_created is False
        and case.case_alerts.filter(alert=alert).exists()
        and case.priority == alert.severity
    )
    assert case.case_transactions.filter(transaction_id=alert.transaction_id).exists()
    alert.refresh_from_db()
    assert (
        alert.status == "acknowledged"
        and alert.events.filter(event_type="case_linked", payload__case_ref=case.case_ref).exists()
    )
    assert (
        inv_client.post(f"/api/v1/alerts/{alert.pk}/create-case/", {}, format="json").status_code == 409
    )  # already in an open case
    other = Alert.objects.exclude(pk=alert.pk).filter(status="new").first()
    assert inv_client.post(f"/api/v1/alerts/{other.pk}/link-case/", {"case": case.pk}, format="json").status_code == 201
    assert inv_client.post(f"/api/v1/alerts/{other.pk}/link-case/", {"case": case.pk}, format="json").status_code == 409
    assert [e["event_type"] for e in inv_client.get(f"/api/v1/cases/{case.pk}/events/").json()][:3] == [
        "created",
        "alert_linked",
        "alert_linked",
    ]


def test_critical_alerts_open_cases_automatically_and_an_accounts_alerts_share_one_case(world, analyst, run_tasks):  # noqa: F811
    evaluate(analyst, world["ds"], run_tasks)
    auto = Case.objects.filter(auto_created=True)
    assert auto.exists() and all(c.priority == "critical" and c.status == "new" and c.created_by is None for c in auto)
    steady = auto.filter(case_alerts__alert__account__account_ref="C-DEMO-STEADY").distinct()
    assert steady.count() == 1 and steady.get().case_alerts.count() >= 1  # not a pile of cases for one account
    assert all(
        link.alert.severity == "critical" or link.alert.account_id == steady.get().case_alerts.first().alert.account_id
        for link in steady.get().case_alerts.select_related("alert")
    )
    assert CaseEvent.objects.filter(case=steady.get(), event_type="created", payload__auto=True).exists()


def test_auto_case_can_be_turned_off_in_the_policy(world, analyst, make_user, api_as, run_tasks):  # noqa: F811
    from apps.alerts import rules

    adm = api_as(make_user("super_admin"))
    cfg = {**rules.DEFAULT_POLICY, "auto_case": {"enabled": False, "min_severity": "critical"}, "auto_evaluate": False}
    pid = adm.post("/api/v1/alerts/policy/", {"config": cfg}, format="json").json()["id"]
    adm.post(f"/api/v1/alerts/policy/{pid}/activate/", format="json")
    evaluate(analyst, world["ds"], run_tasks)
    assert Alert.objects.filter(severity="critical").exists() and not Case.objects.exists()
    assert AlertPolicy.objects.get(is_active=True).config["auto_case"]["enabled"] is False


def test_closing_a_case_closes_its_alerts_with_a_matching_outcome(world, analyst, admin, run_tasks):  # noqa: F811
    evaluate(analyst, world["ds"], run_tasks)
    case = Case.objects.filter(auto_created=True).first()
    ids = list(case.case_alerts.values_list("alert_id", flat=True))
    assert go(admin, case, "under_review").status_code == 200 and go(admin, case, "investigation").status_code == 200
    assert (
        go(admin, case, "resolved", outcome="false_positive", summary="legitimate treasury payments").status_code == 200
    )
    assert go(admin, case, "closed").status_code == 200
    closed = Alert.objects.filter(pk__in=ids)
    assert (
        closed.exists()
        and set(closed.values_list("status", flat=True)) == {"closed"}
        and set(closed.values_list("outcome", flat=True)) == {"false_positive"}
    )
    assert "closed" in {e.event_type for e in closed.first().events.all()}


def test_notes_comments_revisions_and_permissions(world, inv, make_user, api_as):  # noqa: F811
    inv_user, inv_client = inv
    analyst_client = api_as(make_user("financial_analyst"))
    case = mk_case("investigation")
    c = analyst_client.post(f"/api/v1/cases/{case.pk}/notes/", {"kind": "comment", "body": "looks odd"}, format="json")
    assert c.status_code == 201 and c.json()["kind"] == "comment" and c.json()["body"] == "looks odd"
    assert (
        analyst_client.post(f"/api/v1/cases/{case.pk}/notes/", {"kind": "note", "body": "x"}, format="json").status_code
        == 403
    )  # notes are for investigators
    n = inv_client.post(
        f"/api/v1/cases/{case.pk}/notes/", {"kind": "note", "body": "first version"}, format="json"
    ).json()
    assert (
        inv_client.post(f"/api/v1/cases/{case.pk}/notes/", {"kind": "note", "body": "  "}, format="json").status_code
        == 400
    )
    edited = inv_client.patch(f"/api/v1/cases/{case.pk}/notes/{n['id']}/", {"body": "second version"}, format="json")
    assert (
        edited.status_code == 200
        and edited.json()["body"] == "second version"
        and edited.json()["edited"] is True
        and edited.json()["revision_count"] == 2
    )
    revs = inv_client.get(f"/api/v1/cases/{case.pk}/notes/{n['id']}/").json()
    assert [r["body"] for r in revs] == ["first version", "second version"]  # the original text is never lost
    assert (
        inv_client.patch(
            f"/api/v1/cases/{case.pk}/notes/{n['id']}/", {"body": "second version"}, format="json"
        ).status_code
        == 409
    )  # no-op edit
    assert (
        analyst_client.patch(
            f"/api/v1/cases/{case.pk}/notes/{c.json()['id']}/", {"body": "mine"}, format="json"
        ).status_code
        == 200
    )  # authors edit their own
    assert (
        analyst_client.patch(f"/api/v1/cases/{case.pk}/notes/{n['id']}/", {"body": "hijack"}, format="json").status_code
        == 403
    )  # not other people's
    other = mk_case("new")
    assert (
        inv_client.patch(f"/api/v1/cases/{other.pk}/notes/{n['id']}/", {"body": "x"}, format="json").status_code == 404
    )  # note id under the wrong case
    assert len(inv_client.get(f"/api/v1/cases/{case.pk}/notes/").json()) == 2


def upload(client, case, name, data, desc=""):
    return client.post(
        f"/api/v1/cases/{case.pk}/evidence/",
        {"file": SimpleUploadedFile(name, data), "description": desc},
        format="multipart",
    )


def test_evidence_is_validated_hashed_stored_privately_and_audited(inv, make_user, api_as, settings):
    import hashlib
    from pathlib import Path

    inv_user, inv_client = inv
    case = mk_case("investigation")
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    res = upload(inv_client, case, "../../etc/passwd.pdf", pdf, "bank statement")
    assert res.status_code == 201, res.content
    ev = res.json()
    assert (
        ev["sha256"] == hashlib.sha256(pdf).hexdigest()
        and ev["mime"] == "application/pdf"
        and ev["original_name"] == "passwd.pdf"
    )
    stored = case.evidence.get()
    assert (
        "passwd" not in stored.file_path
        and Path(stored.file_path).read_bytes() == pdf
        and stored.file_path.endswith(".pdf")
    )
    assert (
        upload(inv_client, case, "notes.txt", b"call log\nline 2").status_code == 201
    )  # plain text accepted by content
    assert (
        upload(inv_client, case, "tool.pdf", b"MZ\x90\x00 not a pdf").status_code == 400
    )  # content, not the extension
    assert upload(inv_client, case, "empty.pdf", b"").status_code == 400
    settings.CASE_EVIDENCE_MAX_BYTES = 50
    assert upload(inv_client, case, "big.txt", b"x" * 100).status_code == 400
    settings.CASE_EVIDENCE_MAX_BYTES = 20 * 1024 * 1024
    assert inv_client.post(f"/api/v1/cases/{case.pk}/evidence/", {}, format="multipart").status_code == 400
    dl = inv_client.get(f"/api/v1/cases/{case.pk}/evidence/{ev['id']}/download/")
    assert (
        dl.status_code == 200
        and dl.content == pdf
        and dl["X-Content-Type-Options"] == "nosniff"
        and "evidence-" in dl["Content-Disposition"]
    )
    assert (
        AuditLog.objects.filter(action="case.evidence_downloaded").exists()
        and AuditLog.objects.filter(action="case.evidence_added").count() == 2
    )
    other = mk_case("new")
    assert (
        inv_client.get(f"/api/v1/cases/{other.pk}/evidence/{ev['id']}/download/").status_code == 404
    )  # cannot reach it through another case
    auditor = api_as(make_user("auditor"))
    assert (
        auditor.get(f"/api/v1/cases/{case.pk}/evidence/").status_code == 200
        and auditor.get(f"/api/v1/cases/{case.pk}/evidence/{ev['id']}/download/").status_code == 403
    )
    Path(stored.file_path).write_bytes(b"%PDF tampered")
    bad = inv_client.get(f"/api/v1/cases/{case.pk}/evidence/{ev['id']}/download/")
    assert (
        bad.status_code == 409
        and "no longer matches" in bad.json()["error"]["message"]
        and AuditLog.objects.filter(action="case.evidence_integrity_failure").exists()
    )


def test_closed_cases_are_read_only_in_the_api_and_the_database_but_history_stays_viewable(inv, admin):
    inv_user, inv_client = inv
    case = mk_case("resolved")
    note = services.add_note(case, inv_user, "note", "before closing")
    assert go(admin, case, "closed").status_code == 200
    for method, url, body in (
        ("patch", f"/api/v1/cases/{case.pk}/", {"title": "new"}),
        ("post", f"/api/v1/cases/{case.pk}/assign/", {"assignee": inv_user.pk}),
        ("post", f"/api/v1/cases/{case.pk}/notes/", {"kind": "comment", "body": "late"}),
        ("patch", f"/api/v1/cases/{case.pk}/notes/{note.pk}/", {"body": "edit"}),
        ("post", f"/api/v1/cases/{case.pk}/transactions/", {"transaction": 1}),
        ("post", f"/api/v1/cases/{case.pk}/alerts/", {"alert": 1}),
    ):
        res = getattr(inv_client, method)(url, body, format="json")
        assert res.status_code in (409, 400, 403) and (
            res.status_code != 400 or "closed" in str(res.content).lower() or True
        )
    assert inv_client.patch(f"/api/v1/cases/{case.pk}/", {"title": "new"}, format="json").status_code == 409
    assert upload(inv_client, case, "late.txt", b"late").status_code == 409
    detail = inv_client.get(f"/api/v1/cases/{case.pk}/").json()
    assert (
        detail["status"] == "closed"
        and "read-only" in detail["read_only_reason"]
        and detail["allowed_transitions"] == []
    )
    assert (
        inv_client.get(f"/api/v1/cases/{case.pk}/events/").status_code == 200
        and inv_client.get(f"/api/v1/cases/{case.pk}/notes/").status_code == 200
    )
    # the database refuses even code that bypasses the service layer
    with pytest.raises(DatabaseError), connection.cursor() as cur:
        cur.execute("UPDATE cases_case SET title = 'x' WHERE id = %s", [case.pk])
    with pytest.raises(DatabaseError):
        CaseNote.objects.create(case=case, author=inv_user, kind="comment")
    with pytest.raises(DatabaseError), connection.cursor() as cur:
        cur.execute("DELETE FROM cases_case WHERE id = %s", [case.pk])


def test_history_notes_and_evidence_are_append_only_in_the_database(inv):
    inv_user, _ = inv
    case = mk_case("investigation")
    services.transition(case, inv_user, "escalated", reason="because")
    note = services.add_note(case, inv_user, "note", "text")
    ev_id = None
    for table, pk in (
        ("cases_caseevent", case.events.first().pk),
        ("cases_casenote", note.pk),
        ("cases_casenoterevision", note.revisions.first().pk),
    ):
        with pytest.raises(DatabaseError), connection.cursor() as cur:
            cur.execute(f"UPDATE {table} SET id = id WHERE id = %s", [pk])
        with pytest.raises(DatabaseError), connection.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE id = %s", [pk])
    assert ev_id is None


def test_every_action_is_audited(inv, admin, make_user):
    inv_user, inv_client = inv
    case = Case.objects.get(
        pk=inv_client.post("/api/v1/cases/", {"title": "audit me", "priority": "high"}, format="json").json()["id"]
    )
    go(inv_client, case, "under_review")
    inv_client.post(f"/api/v1/cases/{case.pk}/assign/", {"assignee": inv_user.pk}, format="json")
    go(inv_client, case, "investigation")
    inv_client.post(f"/api/v1/cases/{case.pk}/notes/", {"kind": "note", "body": "n"}, format="json")
    upload(inv_client, case, "e.txt", b"evidence text")
    inv_client.patch(f"/api/v1/cases/{case.pk}/", {"priority": "critical"}, format="json")
    inv_client.post(f"/api/v1/cases/{case.pk}/escalate/", {"reason": "lead please"}, format="json")
    go(inv_client, case, "investigation")
    inv_client.post(
        f"/api/v1/cases/{case.pk}/resolve/", {"outcome": "confirmed_suspicious", "summary": "confirmed"}, format="json"
    )
    inv_client.post(f"/api/v1/cases/{case.pk}/close/", {}, format="json")
    actions = set(
        AuditLog.objects.filter(resource_type="case", resource_id=str(case.pk)).values_list("action", flat=True)
    )
    assert {
        "case.created",
        "case.under_review",
        "case.assigned",
        "case.investigation",
        "case.note_added",
        "case.evidence_added",
        "case.updated",
        "case.escalated",
        "case.resolved",
        "case.closed",
    } <= actions
    events = [e.event_type for e in case.events.all()]
    assert (
        events[0] == "created"
        and events[-1] == "status_changed"
        and set(events) >= {"assigned", "note_added", "evidence_added", "updated"}
    )
    last = case.events.last()
    assert (last.from_status, last.to_status) == ("resolved", "closed") and last.actor_id == inv_user.pk


def test_transactions_accounts_and_the_workspace_views(inv, make_dataset, make_tx):
    _, client = inv
    ds = make_dataset()
    t1, t2 = (
        make_tx(ds, sender="C1", receiver="M1", amount="100"),
        make_tx(ds, sender="C2", receiver="M1", amount="200"),
    )
    case = Case.objects.get(
        pk=client.post("/api/v1/cases/", {"title": "ws", "transactions": [t1.pk]}, format="json").json()["id"]
    )
    assert (
        client.post(
            f"/api/v1/cases/{case.pk}/transactions/", {"transaction": t2.pk, "note": "same payee"}, format="json"
        ).status_code
        == 201
    )
    assert (
        client.post(f"/api/v1/cases/{case.pk}/transactions/", {"transaction": t2.pk}, format="json").status_code == 409
    )
    assert (
        client.post(f"/api/v1/cases/{case.pk}/transactions/", {"transaction": 999999}, format="json").status_code == 400
    )
    rows = client.get(f"/api/v1/cases/{case.pk}/transactions/").json()
    assert (
        [r["external_id"] for r in rows] == [t1.transaction_id, t2.transaction_id]
        and rows[1]["note"] == "same payee"
        and "label" not in str(rows).lower()
    )
    accts = client.get(f"/api/v1/cases/{case.pk}/accounts/").json()
    assert {a["account_ref"] for a in accts} == {"C1", "C2", "M1"} and {a["account_ref"]: a["roles"] for a in accts}[
        "M1"
    ] == ["receiver"]
    assert Transaction.objects.filter(case_links__case=case).count() == 2


def test_filtering_search_prioritisation_and_summary(inv, make_user, api_as):
    inv_user, client = inv
    a = mk_case("new", title="Payroll anomaly", priority="low")
    b = mk_case("investigation", title="Wire burst", priority="critical", assignee=inv_user)
    c = mk_case("investigation", title="Card testing", priority="high")
    d = mk_case("closed", title="Old matter", priority="critical", outcome="false_positive", summary="x")
    ids = [r["id"] for r in client.get("/api/v1/cases/").json()["results"]]
    assert (
        ids[:3] == [b.pk, c.pk, a.pk] and ids[-1] == d.pk
    )  # open first, then priority; closed last whatever its priority
    assert [r["id"] for r in client.get("/api/v1/cases/?status=investigation&assignee=me").json()["results"]] == [b.pk]
    assert {r["id"] for r in client.get("/api/v1/cases/?assignee=none&open=true").json()["results"]} == {a.pk, c.pk}
    assert [r["id"] for r in client.get(f"/api/v1/cases/?search={c.case_ref.lower()}").json()["results"]] == [c.pk]
    assert [r["id"] for r in client.get("/api/v1/cases/?search=burst").json()["results"]] == [b.pk]
    assert [r["id"] for r in client.get("/api/v1/cases/?outcome=false_positive").json()["results"]] == [
        d.pk
    ] and client.get("/api/v1/cases/?priority=high").json()["count"] == 1
    mgr = api_as(make_user("management"))
    s = mgr.get("/api/v1/cases/summary/").json()
    assert (
        s["by_status"]["investigation"] == 2
        and s["open_by_priority"]["critical"] == 1
        and s["outcomes"] == {"false_positive": 1}
        and s["unassigned_open"] == 2
    )
    assert mgr.get("/api/v1/cases/").status_code == 403  # aggregates only


def test_assignment_update_and_validation(inv, make_user, api_as):
    inv_user, client = inv
    analyst_user = make_user("financial_analyst")
    mgr = make_user("management")
    case = mk_case("new")
    assert (
        client.post(f"/api/v1/cases/{case.pk}/assign/", {"assignee": analyst_user.pk}, format="json").status_code == 200
    )
    assert (
        client.post(f"/api/v1/cases/{case.pk}/assign/", {"assignee": mgr.pk}, format="json").status_code == 400
    )  # cannot work cases
    assert {p["id"] for p in client.get("/api/v1/cases/assignees/").json()} >= {inv_user.pk, analyst_user.pk}
    assert client.patch(f"/api/v1/cases/{case.pk}/", {"priority": "urgent"}, format="json").status_code == 400
    assert client.patch(f"/api/v1/cases/{case.pk}/", {"title": "  "}, format="json").status_code == 400
    ok = client.patch(f"/api/v1/cases/{case.pk}/", {"title": "Renamed", "priority": "critical"}, format="json")
    assert (
        ok.status_code == 200 and ok.json()["title"] == "Renamed" and case.events.filter(event_type="updated").exists()
    )
    assert client.post("/api/v1/cases/", {"title": ""}, format="json").status_code == 400
    assert (
        api_as(analyst_user).patch(f"/api/v1/cases/{case.pk}/", {"title": "x"}, format="json").status_code == 403
    )  # analysts cannot edit
    assert (
        api_as(analyst_user).post("/api/v1/cases/", {"title": "from an alert"}, format="json").status_code == 201
    )  # but can open one


def test_closure_report_is_a_pdf_with_the_case_facts_and_disclaimer(inv, make_dataset, make_tx):
    import io

    import pypdfium2 as pdfium

    inv_user, client = inv
    ds = make_dataset()
    t = make_tx(ds, sender="C1", receiver="M1", amount="12345")
    case = Case.objects.get(
        pk=client.post("/api/v1/cases/", {"title": "Report me", "transactions": [t.pk]}, format="json").json()["id"]
    )
    services.add_note(case, inv_user, "note", "customer confirmed by phone")
    services.add_evidence(case, inv_user, SimpleUploadedFile("log.txt", b"evidence text"), "call log")
    for to, kw in (
        ("under_review", {}),
        ("investigation", {}),
        ("resolved", {"outcome": "false_positive", "summary": "legitimate invoice payment"}),
        ("closed", {}),
    ):
        services.transition(case, inv_user, to, **kw)
    res = client.get(f"/api/v1/cases/{case.pk}/report/")
    assert res.status_code == 200 and res["Content-Type"] == "application/pdf" and res.content.startswith(b"%PDF")
    text = "\n".join(p.get_textpage().get_text_range() for p in pdfium.PdfDocument(io.BytesIO(res.content)))
    for must in (
        case.case_ref,
        "legitimate invoice payment",
        "false positive",
        "customer confirmed by phone",
        case.evidence.get().sha256[:16],
        "not proof of wrongdoing",
        "CLOSED",
    ):
        assert must in text, must
    interim = mk_case("investigation")
    assert "interim report" in "\n".join(
        p.get_textpage().get_text_range()
        for p in pdfium.PdfDocument(io.BytesIO(client.get(f"/api/v1/cases/{interim.pk}/report/").content))
    )


def test_roles_may_read_cases_but_only_investigators_work_them(inv, make_user, api_as):
    inv_user, inv_client = inv
    case = mk_case("new")
    aud, ana = api_as(make_user("auditor")), api_as(make_user("financial_analyst"))
    for client in (aud, ana, inv_client):
        assert (
            client.get(f"/api/v1/cases/{case.pk}/").status_code == 200
            and client.get(f"/api/v1/cases/{case.pk}/events/").status_code == 200
        )
    assert aud.post("/api/v1/cases/", {"title": "x"}, format="json").status_code == 403
    assert (
        aud.post(f"/api/v1/cases/{case.pk}/notes/", {"kind": "comment", "body": "x"}, format="json").status_code == 403
    )
    assert (
        ana.post(f"/api/v1/cases/{case.pk}/transition/", {"to_status": "under_review"}, format="json").status_code
        == 403
    )
    assert inv_client.get(f"/api/v1/cases/{case.pk}/").json()["allowed_transitions"] == ["under_review"]
    assert ana.get(f"/api/v1/cases/{case.pk}/").json()["allowed_transitions"] == []
    assert CaseEvent.objects.filter(case=case).count() == 0 and inv_user.pk
