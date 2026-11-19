import pytest

from apps.model_registry.models import ModelEvaluation, ModelVersion
from apps.model_registry.services import register_results


def results(sha="a" * 64, pr=0.5):
    return {
        "run": "lr_test",
        "dataset": "paysim",
        "algorithm": "LogisticRegression",
        "artifact": "/datasets/artifacts/x/model.joblib",
        "artifact_sha256": sha,
        "seed": 42,
        "raw_sha256": "b" * 64,
        "features": ["a", "b"],
        "feature_set": "core",
        "metrics": {"train": {"pr_auc": 0.9}, "test": {"pr_auc": pr}, "latency": {"single_ms_median": 1.0}},
    }


@pytest.mark.django_db
def test_register_is_idempotent_and_hash_versioned():
    a = register_results(results())
    b = register_results(results(pr=0.6))  # same artifact -> same version, evaluations refreshed
    assert a.pk == b.pk and ModelVersion.objects.count() == 1
    assert ModelEvaluation.objects.filter(version=a).count() == 3
    assert ModelEvaluation.objects.get(version=a, split_name="test").metrics["pr_auc"] == 0.6
    c = register_results(results(sha="c" * 64))  # new artifact -> new version of the same model
    assert c.pk != a.pk and c.model_id == a.model_id
    assert a.training_data_sha256 == "b" * 64 and a.random_seed == 42


@pytest.mark.django_db
def test_register_rejects_incomplete_results():
    bad = results()
    del bad["artifact_sha256"]
    with pytest.raises(ValueError):
        register_results(bad)
