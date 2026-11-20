"""N+1 guard: list endpoints must run the same number of SQL queries for 3 rows as for 20 rows (Phase 15, NFR-02)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.alerts.models import Alert
from apps.audit.models import AuditLog
from apps.cases import services as case_services
from apps.cases.models import Case

pytestmark = pytest.mark.django_db


def _queries(client, url: str) -> tuple[int, int]:
    with CaptureQueriesContext(connection) as ctx:
        res = client.get(url)
    assert res.status_code == 200, url
    return len(ctx), len(res.json()["results"])


def _check(client, url: str, add_rows, small: int = 3, large: int = 20) -> None:
    add_rows(small)
    _queries(client, url)  # warm-up: per-user permission cache and similar one-off lookups
    q_small, n_small = _queries(client, url)
    add_rows(large - small)
    q_large, n_large = _queries(client, url)
    assert n_large > n_small >= small, (n_small, n_large)
    assert q_large == q_small, f"{url}: {q_small} queries for {n_small} rows but {q_large} for {n_large} (N+1)"


def test_transactions_list_has_constant_queries(make_user, api_as, make_dataset, make_tx):
    ds = make_dataset()
    _check(
        api_as(make_user("financial_analyst")),
        f"/api/v1/transactions/?dataset={ds.id}",
        lambda n: [make_tx(ds, sender=f"C{i}", receiver=f"R{i}") for i in range(n)],
    )


def test_alerts_list_has_constant_queries(make_user, api_as, make_dataset, make_tx):
    ds = make_dataset()
    counter = {"n": 0}

    def add(n):
        for _ in range(n):
            counter["n"] += 1
            tx = make_tx(ds, sender=f"A{counter['n']}")
            Alert.objects.create(
                alert_type="high_value",
                severity="high",
                dedup_key=f"k{counter['n']}",
                dataset=ds,
                transaction=tx,
                account=tx.sender,
                reason="r",
            )

    _check(api_as(make_user("financial_analyst")), "/api/v1/alerts/", add)


def test_cases_list_has_constant_queries(make_user, api_as):
    def add(n):
        for _ in range(n):
            Case.objects.create(case_ref=case_services.next_case_ref(), title="t")

    _check(api_as(make_user("fraud_investigator")), "/api/v1/cases/", add)


def test_audit_log_list_has_constant_queries(make_user, api_as):
    def add(n):
        for i in range(n):
            AuditLog.objects.create(action="x.y", actor_email=f"u{i}@example.com")

    # the signed-in user's own login is not audited here (force_authenticate), so rows come only from `add`
    _check(api_as(make_user("auditor")), "/api/v1/audit/logs/", add)


def test_users_list_has_constant_queries(make_user, api_as):
    admin = make_user("super_admin")
    _check(api_as(admin), "/api/v1/users/", lambda n: [make_user("auditor") for _ in range(n)])


def test_imports_list_has_constant_queries(make_user, api_as, make_dataset):
    from apps.datasets.models import ImportJob

    ds = make_dataset()
    _check(
        api_as(make_user("financial_analyst")),
        "/api/v1/imports/",
        lambda n: [ImportJob.objects.create(dataset=ds, file_name=f"f{i}.csv", status="completed") for i in range(n)],
    )


def test_detection_runs_list_has_constant_queries(make_user, api_as, make_dataset):
    from apps.detection.models import DetectionRun
    from apps.model_registry.services import register_results

    ds = make_dataset()
    mv = register_results(
        {
            "run": "qc_model",
            "dataset": "paysim",
            "algorithm": "LogisticRegression",
            "artifact": "/x/m.joblib",
            "artifact_sha256": "a" * 64,
            "seed": 1,
            "raw_sha256": "b" * 64,
            "features": ["log_amount"],
            "metrics": {"validation": {"at_validation_threshold": {"threshold": 0.5}}, "latency": {}},
        }
    )
    _check(
        api_as(make_user("financial_analyst")),
        "/api/v1/detection/runs/",
        lambda n: [
            DetectionRun.objects.create(model_version=mv, dataset=ds, threshold=0.5, threshold_source="t")
            for _ in range(n)
        ],
    )
