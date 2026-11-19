"""Alerts: rules from stored results, deduplication, lifecycle, prioritisation, permissions, notifications."""

import socketserver
import threading

import pytest
from django.core import mail
from django.db import DatabaseError, connection

from apps.alerts import rules, services
from apps.alerts.models import Alert, AlertEvent, AlertPolicy, AlertRun, NotificationLog
from apps.audit.models import AuditLog
from apps.behavior import scenario
from apps.behavior import services as behavior_services
from apps.detection.models import DetectionRun
from apps.duplicates import services as dup_services
from apps.duplicates.models import DuplicateScanRun
from apps.graph_engine import services as graph_services
from apps.risk_engine import services as risk_services
from apps.transactions.models import Transaction
from tests.test_risk import make_detection

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(make_user):
    return make_user("financial_analyst")


@pytest.fixture
def analyst(user, api_as):
    return api_as(user)


@pytest.fixture
def world(user):
    """DEMO burst scenario with every engine run (behaviour, graph, duplicates, detection) and a risk run."""
    ds = scenario.build()
    burst = list(
        Transaction.objects.filter(dataset=ds, receiver__account_ref="NEW-PAYEE-X").values_list("id", flat=True)
    )
    brun = behavior_services.create_run(dataset=ds, user=user)
    behavior_services.execute_run(brun.pk)
    snap = graph_services.create_snapshot(dataset=ds, user=user, as_of=None, window_days=None)
    graph_services.execute_snapshot(snap.pk)
    scan = DuplicateScanRun.objects.create(kind="transaction", dataset=ds, created_by=user)
    dup_services.execute_scan(scan.pk)
    make_detection(ds, user, set(burst))
    rrun = risk_services.start_run(dataset=ds, user=user)
    risk_services.execute_run(rrun.pk)
    return {"ds": ds, "burst": burst, "risk_run": rrun}


def evaluate(api, ds, run_tasks):
    with run_tasks(execute=True):
        res = api.post("/api/v1/alerts/evaluate/", {"dataset": ds.pk}, format="json")
    assert res.status_code == 202, res.content
    return AlertRun.objects.get(pk=res.data["id"])


def types(qs=None):
    return {a.alert_type for a in (qs if qs is not None else Alert.objects.all())}


def test_rules_create_the_expected_alert_types_from_stored_results(world, analyst, run_tasks):
    run = evaluate(analyst, world["ds"], run_tasks)
    assert run.status == "succeeded" and run.result["created"] > 0 and run.result["created"] == Alert.objects.count()
    assert {"high_risk", "multiple_transactions", "unusual_activity", "duplicate_record"} <= types()
    assert (
        "behavior_change" in types() and "failed_transactions" not in types() and "high_value" not in types()
    )  # no status data, low amounts vs 1,000,000
    burst_alert = Alert.objects.get(alert_type="multiple_transactions")
    assert burst_alert.severity == "critical" and burst_alert.account.account_ref == "C-DEMO-STEADY"
    assert burst_alert.evidence_snapshot["transactions_in_window"] == 3  # the evidence is what it was at creation...
    assert (
        burst_alert.events.get(event_type="severity_raised").payload["evidence"]["transactions_in_window"] == 5
    )  # ...growth is history
    risk_alert = Alert.objects.filter(alert_type="high_risk").first()
    assert (
        risk_alert.assessment_id
        and risk_alert.evidence_snapshot["components"]["A"]["available"]
        and risk_alert.evidence_snapshot["signals"] == ["risk"]
    )
    dup = Alert.objects.filter(alert_type="duplicate_record").first()
    assert dup.evidence_snapshot["match_class"] in ("exact", "strong_similar") and dup.transaction_id in world["burst"]
    assert all(
        a.status == "new" and a.policy_version == 1 and a.events.filter(event_type="created").count() == 1
        for a in Alert.objects.all()
    )


def test_acceptance_a_repeated_event_creates_one_alert(world, analyst, run_tasks):
    first = evaluate(analyst, world["ds"], run_tasks)
    count, events = Alert.objects.count(), AlertEvent.objects.count()
    second = evaluate(analyst, world["ds"], run_tasks)  # the same results again
    assert (
        second.result["created"] == 0
        and second.result["deduplicated"] >= first.result["created"] - first.result["raised"]
    )
    assert Alert.objects.count() == count and AlertEvent.objects.count() == events  # no new alerts, no new history
    keys = list(Alert.objects.values_list("dedup_key", flat=True))
    assert len(keys) == len(set(keys))


def test_a_burst_is_one_alert_per_bucket_whose_severity_rises_in_place(world, analyst, run_tasks):
    evaluate(analyst, world["ds"], run_tasks)
    bursts = Alert.objects.filter(alert_type="multiple_transactions")
    assert bursts.count() == 1  # transactions 3, 4 and 5 of the burst share one alert
    events = list(bursts.get().events.values_list("event_type", flat=True))
    assert events == ["created", "severity_raised"] and bursts.get().severity == "critical"
    raised = bursts.get().events.get(event_type="severity_raised").payload
    assert raised["from"] == "high" and raised["to"] == "critical"


def test_acceptance_a_meaningfully_new_reason_creates_a_new_alert(world, analyst, user, run_tasks):
    evaluate(analyst, world["ds"], run_tasks)
    last = Transaction.objects.filter(pk__in=world["burst"]).order_by("-occurred_at").first()
    same_tx = Alert.objects.filter(transaction=last)
    assert {"high_risk", "unusual_activity"} <= types(
        same_tx
    )  # different reasons about the same transaction are separate alerts
    assert len({a.dedup_key for a in same_tx}) == same_tx.count()
    a = Alert.objects.get(alert_type="high_risk", transaction=last)
    services.close(a, user, "false_positive", "reviewed")  # once closed, the same condition may raise a fresh alert
    evaluate(analyst, world["ds"], run_tasks)
    again = Alert.objects.filter(dedup_key=a.dedup_key)
    assert (
        again.count() == 2
        and again.exclude(status="closed").count() == 1
        and again.filter(status="closed").get().pk == a.pk
    )


def test_evidence_snapshot_is_preserved_when_severity_changes(world, analyst, run_tasks):
    evaluate(analyst, world["ds"], run_tasks)
    burst = Alert.objects.get(alert_type="multiple_transactions")
    snapshot = dict(burst.evidence_snapshot)
    assert snapshot["transactions_in_window"] >= 3
    burst.refresh_from_db()
    assert (
        burst.evidence_snapshot == snapshot
    )  # the severity raise happened but the evidence is what it was at creation
    assert (
        analyst.get(f"/api/v1/alerts/{burst.pk}/").json()["evidence_snapshot"] == snapshot
    )  # the API serves the preserved copy


def test_lifecycle_transitions_are_validated_and_recorded(world, analyst, make_user, api_as, run_tasks):
    evaluate(analyst, world["ds"], run_tasks)
    alert = Alert.objects.filter(alert_type="duplicate_record").first()
    url = f"/api/v1/alerts/{alert.pk}"
    ack = analyst.post(f"{url}/acknowledge/", {}, format="json")
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged" and ack.json()["acknowledged_at"]
    assert analyst.post(f"{url}/acknowledge/", {}, format="json").status_code == 409  # already acknowledged
    assert analyst.post(f"{url}/escalate/", {"reason": "   "}, format="json").status_code == 400
    esc = analyst.post(f"{url}/escalate/", {"reason": "customer unreachable"}, format="json")
    assert (
        esc.status_code == 200
        and esc.json()["status"] == "escalated"
        and esc.json()["escalation_reason"] == "customer unreachable"
    )
    assert analyst.post(f"{url}/escalate/", {"reason": "again"}, format="json").status_code == 409
    assert analyst.post(f"{url}/close/", {"outcome": "bogus"}, format="json").status_code == 400
    closed = analyst.post(
        f"{url}/close/", {"outcome": "true_positive", "notes": "confirmed with customer"}, format="json"
    )
    assert (
        closed.status_code == 200
        and closed.json()["status"] == "closed"
        and closed.json()["outcome"] == "true_positive"
    )
    assert analyst.post(f"{url}/close/", {"outcome": "other"}, format="json").status_code == 409
    assert analyst.post(f"{url}/acknowledge/", {}, format="json").status_code == 409
    events = [e["event_type"] for e in analyst.get(f"{url}/events/").json()]
    assert events == ["created", "acknowledged", "escalated", "closed"]
    assert {"alert.acknowledged", "alert.escalated", "alert.closed"} <= set(
        AuditLog.objects.values_list("action", flat=True)
    )


def test_assignment_only_to_eligible_users_never_on_closed_alerts(world, analyst, make_user, run_tasks):
    inv = make_user("fraud_investigator")
    mgr = make_user("management")
    evaluate(analyst, world["ds"], run_tasks)
    alert = Alert.objects.first()
    people = {p["id"] for p in analyst.get("/api/v1/alerts/assignees/").json()}
    assert inv.pk in people and mgr.pk not in people
    ok = analyst.post(f"/api/v1/alerts/{alert.pk}/assign/", {"assignee": inv.pk}, format="json")
    assert ok.status_code == 200 and ok.json()["assignee_email"] == inv.email
    assert analyst.post(f"/api/v1/alerts/{alert.pk}/assign/", {"assignee": mgr.pk}, format="json").status_code == 400
    services.close(alert, inv, "other", "")
    assert analyst.post(f"/api/v1/alerts/{alert.pk}/assign/", {"assignee": inv.pk}, format="json").status_code == 409
    assert alert.events.filter(event_type="assigned").count() == 1


def test_alert_history_is_append_only_in_the_database(world, analyst, run_tasks):
    evaluate(analyst, world["ds"], run_tasks)
    ev = AlertEvent.objects.first()
    with pytest.raises(DatabaseError), connection.cursor() as cur:
        cur.execute("UPDATE alerts_alertevent SET event_type = 'x' WHERE id = %s", [ev.pk])
    with pytest.raises(DatabaseError), connection.cursor() as cur:
        cur.execute("DELETE FROM alerts_alertevent WHERE id = %s", [ev.pk])


def test_prioritisation_filters_and_summary(world, analyst, user, run_tasks):
    evaluate(analyst, world["ds"], run_tasks)
    rows = analyst.get("/api/v1/alerts/?page_size=100").json()["results"]
    rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    sev = [rank[r["severity"]] for r in rows]
    assert sev == sorted(sev, reverse=True)  # critical first
    closed = Alert.objects.filter(severity="critical").first()
    services.close(closed, user, "other", "")
    after = analyst.get("/api/v1/alerts/?page_size=100").json()["results"]
    assert after[-1]["id"] == closed.pk or after[-1]["status"] == "closed"  # closed alerts sink to the bottom
    assert all(
        r["severity"] == "high" for r in analyst.get("/api/v1/alerts/?severity=high&open=true").json()["results"]
    )
    assert {r["alert_type"] for r in analyst.get("/api/v1/alerts/?alert_type=duplicate_record").json()["results"]} == {
        "duplicate_record"
    }
    assert (
        analyst.get("/api/v1/alerts/?assignee=none&open=true").json()["count"]
        == Alert.objects.exclude(status="closed").count()
    )
    assert analyst.get("/api/v1/alerts/?assignee=me").json()["count"] == 0
    assert analyst.get("/api/v1/alerts/?category=critical").status_code == 200
    s = analyst.get("/api/v1/alerts/summary/").json()
    assert (
        sum(s["open_by_severity"].values()) == Alert.objects.exclude(status="closed").count()
        and s["by_status"]["closed"] == 1
    )
    detail = analyst.get(f"/api/v1/alerts/{rows[0]['id']}/").json()
    assert (
        detail["evidence_snapshot"]
        and detail["dedup_key"]
        and analyst.get(f"/api/v1/transactions/{rows[0]['transaction']}/alerts/").status_code == 200
    )
    assert "ground_truth" not in str(detail)


def test_permissions_per_role(world, analyst, make_user, api_as, run_tasks):
    evaluate(analyst, world["ds"], run_tasks)
    a = Alert.objects.first()
    aud, inv, mgr, adm = (api_as(make_user(r)) for r in ("auditor", "fraud_investigator", "management", "super_admin"))
    assert (
        aud.get("/api/v1/alerts/").status_code == 200
        and aud.post(f"/api/v1/alerts/{a.pk}/acknowledge/", {}, format="json").status_code == 403
    )
    assert (
        mgr.get("/api/v1/alerts/").status_code == 403 and mgr.get("/api/v1/alerts/summary/").status_code == 200
    )  # aggregate only
    assert inv.post(f"/api/v1/alerts/{a.pk}/acknowledge/", {}, format="json").status_code == 200
    assert inv.post("/api/v1/alerts/evaluate/", {"dataset": world["ds"].pk}, format="json").status_code == 403
    assert analyst.post("/api/v1/alerts/policy/", {"config": rules.DEFAULT_POLICY}, format="json").status_code == 403
    assert adm.post("/api/v1/alerts/policy/", {"config": rules.DEFAULT_POLICY}, format="json").status_code == 201


def test_policy_validation_versioning_and_effect(world, make_user, api_as, analyst, run_tasks):
    adm = api_as(make_user("super_admin"))
    bad = {**rules.DEFAULT_POLICY, "high_risk": {"enabled": True, "min_category": "severe"}}
    r = adm.post("/api/v1/alerts/policy/", {"config": bad}, format="json")
    assert r.status_code == 400 and "min_category" in r.json()["error"]["message"]
    for broken in (
        {**rules.DEFAULT_POLICY, "dedup_bucket_hours": 0},
        {k: v for k, v in rules.DEFAULT_POLICY.items() if k != "email"},
        {**rules.DEFAULT_POLICY, "email": {"min_severity": "high", "recipients": ["nobody"]}},
        {**rules.DEFAULT_POLICY, "multiple_transactions": {"enabled": True, "min_transactions": 5, "critical_at": 3}},
    ):
        assert adm.post("/api/v1/alerts/policy/", {"config": broken}, format="json").status_code == 400
    quiet = {
        **rules.DEFAULT_POLICY,
        "multiple_transactions": {**rules.DEFAULT_POLICY["multiple_transactions"], "enabled": False},
        "auto_evaluate": False,
    }
    created = adm.post("/api/v1/alerts/policy/", {"config": quiet, "notes": "no burst alerts"}, format="json")
    assert created.status_code == 201 and created.json()["version"] == 2 and created.json()["is_active"] is False
    assert (
        adm.post(f"/api/v1/alerts/policy/{created.json()['id']}/activate/", format="json").json()["is_active"] is True
    )
    assert list(AlertPolicy.objects.filter(is_active=True).values_list("version", flat=True)) == [2]
    run = evaluate(analyst, world["ds"], run_tasks)
    assert run.policy_version == 2 and "multiple_transactions" not in types() and "high_risk" in types()


def test_high_value_and_failed_transaction_rules(make_dataset, make_tx, analyst, make_user, api_as, run_tasks):
    ds = make_dataset()
    make_tx(ds, sender="C1", receiver="M1", amount="2000000")  # above 1,000,000
    make_tx(ds, sender="C1", receiver="M1", amount="9000000")  # above 5x the threshold
    make_tx(ds, sender="C1", receiver="M1", amount="500")
    for _ in range(3):
        make_tx(ds, sender="C2", receiver="M2", amount="10", status="failed")
    run = evaluate(analyst, ds, run_tasks)
    hv = Alert.objects.filter(alert_type="high_value")
    assert sorted(a.severity for a in hv) == ["high", "medium"] and hv.count() == 2
    fails = Alert.objects.get(alert_type="failed_transactions")
    assert fails.evidence_snapshot["failed_count"] == 3 and run.result["by_type"]["failed_transactions"] == 1
    clean = make_dataset()
    make_tx(
        clean, sender="C3", receiver="M3", amount="10"
    )  # status data present only as 'completed': the rule does not apply
    evaluate(analyst, clean, run_tasks)
    assert not Alert.objects.filter(dataset=clean, alert_type="failed_transactions").exists()


def test_rapid_fund_movement_and_suspicious_beneficiary_from_graph_findings(
    make_dataset, make_tx, user, analyst, run_tasks
):
    from datetime import UTC, datetime, timedelta

    ds = make_dataset()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i, (s, r) in enumerate([("B1", "B2"), ("B2", "B3"), ("B3", "B4"), ("B4", "B5")]):
        make_tx(ds, sender=s, receiver=r, amount=str(90000 - i * 1000), occurred_at=base + timedelta(minutes=10 * i))
    for i in range(8):
        make_tx(ds, sender=f"FS{i}", receiver="F0", amount="2000", occurred_at=base + timedelta(days=1, minutes=15 * i))
    for i in range(60):  # background so the fan-in stands out
        make_tx(ds, sender=f"X{i}", receiver=f"Y{i}", amount="10", occurred_at=base + timedelta(days=2, minutes=i))
    snap = graph_services.create_snapshot(dataset=ds, user=user, as_of=None, window_days=None)
    graph_services.execute_snapshot(snap.pk)
    evaluate(analyst, ds, run_tasks)
    chain = Alert.objects.get(alert_type="rapid_fund_movement")
    assert chain.evidence_snapshot["evidence"]["hops"] == 4 and chain.severity in ("medium", "high", "critical")
    ben = Alert.objects.filter(alert_type="suspicious_beneficiary")
    assert ben.count() == 1 and ben.get().account.account_ref == "F0"


# ---------------------------------------------------------------- notifications
def configure_email(make_user, api_as, recipients, min_severity="high"):
    adm = api_as(make_user("super_admin"))
    cfg = {
        **rules.DEFAULT_POLICY,
        "email": {"min_severity": min_severity, "recipients": recipients},
        "auto_evaluate": False,
    }
    pid = adm.post("/api/v1/alerts/policy/", {"config": cfg}, format="json").json()["id"]
    adm.post(f"/api/v1/alerts/policy/{pid}/activate/", format="json")


def test_email_is_sent_for_severe_alerts_without_amounts_and_logged(
    world, analyst, make_user, api_as, run_tasks, settings
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    configure_email(make_user, api_as, ["oncall@example.com"], "critical")
    evaluate(analyst, world["ds"], run_tasks)
    sent = [m for m in mail.outbox if m.to == ["oncall@example.com"]]
    assert sent and len(sent) >= Alert.objects.filter(severity="critical").count()
    assert all(
        m.subject.startswith("[FinGuard] CRITICAL alert #") for m in sent
    )  # only the severity threshold is mailed
    m = sent[0]
    assert (
        m.subject.startswith("[FinGuard] CRITICAL alert #")
        and "/alerts?open=" in m.body
        and "not a finding of wrongdoing" in m.body
    )
    assert (
        "40000" not in m.body and "40,000" not in m.body and "C-DEMO" not in m.body
    )  # nothing sensitive leaves the system
    logs = NotificationLog.objects.filter(channel="email")
    assert (
        logs.filter(status="sent", recipient="oncall@example.com").count() == len(sent)
        and logs.filter(status="skipped").exists()
    )  # lower severities skipped


def test_a_failing_email_is_logged_and_never_blocks_the_alert(
    world, analyst, make_user, api_as, run_tasks, settings, monkeypatch
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    configure_email(make_user, api_as, ["oncall@example.com"], "low")

    def boom(*a, **k):
        raise OSError("smtp down")

    monkeypatch.setattr("django.core.mail.send_mail", boom)
    run = evaluate(analyst, world["ds"], run_tasks)
    assert run.status == "succeeded" and Alert.objects.count() == run.result["created"]
    failed = NotificationLog.objects.filter(channel="email", status="failed")
    assert failed.exists() and "smtp down" in failed.first().error


class _FakeSmtp(socketserver.StreamRequestHandler):
    received: list[str] = []

    def handle(self):
        w = lambda s: self.wfile.write((s + "\r\n").encode())  # noqa: E731
        w("220 test ESMTP")
        data, in_data = [], False
        for raw in self.rfile:
            line = raw.decode().rstrip("\r\n")
            if in_data:
                if line == ".":
                    in_data = False
                    type(self).received.append("\n".join(data))
                    w("250 queued")
                else:
                    data.append(line)
                continue
            cmd = line.upper()
            if cmd.startswith(("EHLO", "HELO")):
                w("250 test")
            elif cmd == "DATA":
                in_data = True
                w("354 go")
            elif cmd == "QUIT":
                w("221 bye")
                return
            else:
                w("250 ok")


def test_smtp_delivery_over_the_wire(world, analyst, make_user, api_as, run_tasks, settings):
    _FakeSmtp.received = []
    server = socketserver.TCPServer(("127.0.0.1", 0), _FakeSmtp)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST, settings.EMAIL_PORT, settings.EMAIL_USE_TLS = "127.0.0.1", server.server_address[1], False
        configure_email(make_user, api_as, ["soc@example.com"], "critical")
        evaluate(analyst, world["ds"], run_tasks)
    finally:
        server.shutdown()
        server.server_close()
    assert _FakeSmtp.received, "the message never reached the SMTP server"
    wire = _FakeSmtp.received[0]
    assert (
        "Subject: [FinGuard] CRITICAL alert #" in wire
        and "/alerts?open=" in wire
        and "not a finding of wrongdoing" in wire
    )
    assert NotificationLog.objects.filter(channel="email", status="sent", recipient="soc@example.com").exists()


def test_alerts_are_evaluated_automatically_when_a_risk_run_finishes(world, user, django_capture_on_commit_callbacks):
    from config.celery import app

    app.conf.task_always_eager = True
    try:
        before = AlertRun.objects.count()
        with django_capture_on_commit_callbacks(execute=True):
            rrun = risk_services.start_run(dataset=world["ds"], user=user)
            risk_services.execute_run(rrun.pk)
    finally:
        app.conf.task_always_eager = False
    auto = AlertRun.objects.filter(trigger="risk_run", source_risk_run=rrun.pk)
    assert AlertRun.objects.count() > before and auto.count() == 1 and auto.get().status == "succeeded"
    # a second save of the same finished run must not start another evaluation
    rrun.save()
    assert AlertRun.objects.filter(source_risk_run=rrun.pk).count() == 1
    assert DetectionRun.objects.exists()


def test_no_automatic_evaluation_when_the_policy_turns_it_off(world, user, django_capture_on_commit_callbacks):
    pol = AlertPolicy.objects.get(is_active=True)
    AlertPolicy.objects.filter(pk=pol.pk).update(config={**pol.config, "auto_evaluate": False})
    with django_capture_on_commit_callbacks(execute=True):
        rrun = risk_services.start_run(dataset=world["ds"], user=user)
        risk_services.execute_run(rrun.pk)
    assert not AlertRun.objects.filter(source_risk_run=rrun.pk).exists()


@pytest.mark.django_db(transaction=True)
async def test_websocket_push_reaches_alert_readers_only(settings):
    from asgiref.sync import sync_to_async
    from channels import layers
    from channels.testing import WebsocketCommunicator
    from django.core.cache import cache

    from apps.accounts.models import Role, User
    from apps.datasets.models import Dataset
    from config.asgi import application

    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    layers.channel_layers.backends = {}

    async def user(role, email):
        return await sync_to_async(User.objects.create_user)(
            email=email, password="Correct-Horse-Battery-9", role=await Role.objects.aget(name=role), full_name=email
        )

    reader, manager = await user("financial_analyst", "r@example.com"), await user("management", "m@example.com")
    cache.set("wsticket:r", reader.pk, 30)
    cache.set("wsticket:m", manager.pk, 30)
    cr, cm = (
        WebsocketCommunicator(application, "/ws/events/?ticket=r"),
        WebsocketCommunicator(application, "/ws/events/?ticket=m"),
    )
    assert (await cr.connect())[0] and (await cm.connect())[0]
    ds = await sync_to_async(Dataset.objects.create)(name="MOCK ws alerts")

    def make_alert():
        a = Alert.objects.create(alert_type="high_value", severity="high", dedup_key="ws:1", dataset=ds, reason="r")
        services._publish(a, "alert.created")
        return a

    alert = await sync_to_async(make_alert)()
    msg = await cr.receive_json_from(timeout=2)
    assert msg["type"] == "alert.created" and msg["data"]["id"] == alert.pk and msg["data"]["severity"] == "high"
    assert await cm.receive_nothing(timeout=0.3)  # a role without alerts.read gets nothing
    await cr.disconnect()
    await cm.disconnect()
    layers.channel_layers.backends = {}


def test_a_loose_threshold_cannot_flood_the_queue_the_cap_keeps_the_most_important(
    make_dataset, make_tx, make_user, api_as, analyst, run_tasks
):
    ds = make_dataset()
    for i in range(30):
        make_tx(ds, sender=f"C{i}", receiver="M1", amount=str(1_000_000 + i * 1000))  # all above the threshold
    adm = api_as(make_user("super_admin"))
    cfg = {**rules.DEFAULT_POLICY, "max_alerts_per_rule": 10, "auto_evaluate": False}
    adm.post(
        f"/api/v1/alerts/policy/{adm.post('/api/v1/alerts/policy/', {'config': cfg}, format='json').json()['id']}/activate/",
        format="json",
    )
    run = evaluate(analyst, ds, run_tasks)
    assert run.result["created"] == 10 and run.result["suppressed"] == {
        "high_value": 20
    }  # the cut is reported, not hidden
    kept = sorted(float(a.evidence_snapshot["amount"]) for a in Alert.objects.filter(alert_type="high_value"))
    assert kept == [1_000_000 + i * 1000 for i in range(20, 30)]  # the ten largest amounts survived
    assert (
        adm.post("/api/v1/alerts/policy/", {"config": {**cfg, "max_alerts_per_rule": 0}}, format="json").status_code
        == 400
    )
