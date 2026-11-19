from django.db import migrations

FORWARD = """
CREATE FUNCTION alerts_alertevent_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'alerts_alertevent is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER alerts_alertevent_no_update_delete
BEFORE UPDATE OR DELETE ON alerts_alertevent
FOR EACH ROW EXECUTE FUNCTION alerts_alertevent_immutable();
"""
REVERSE = """
DROP TRIGGER alerts_alertevent_no_update_delete ON alerts_alertevent;
DROP FUNCTION alerts_alertevent_immutable();
"""
DEFAULT = {
    "high_risk": {"enabled": True, "min_category": "high"},
    "multiple_transactions": {"enabled": True, "min_transactions": 3, "critical_at": 5},
    "unusual_activity": {"enabled": True, "min_score": 70},
    "suspicious_beneficiary": {"enabled": True, "min_score": 50},
    "failed_transactions": {"enabled": True, "min_count": 3},
    "high_value": {"enabled": True, "amount": 1000000, "critical_multiple": 5},
    "rapid_fund_movement": {"enabled": True, "min_score": 40},
    "behavior_change": {"enabled": True, "min_score": 60},
    "duplicate_record": {"enabled": True, "min_class": "strong_similar"},
    "dedup_bucket_hours": 24,
    "email": {"min_severity": "high", "recipients": []},
    "auto_evaluate": True,
    "max_alerts_per_rule": 500,
}


def seed_default(apps, schema_editor):
    AlertPolicy = apps.get_model("alerts", "AlertPolicy")
    if not AlertPolicy.objects.exists():
        AlertPolicy.objects.create(
            version=1, config=DEFAULT, is_active=True, notes="Initial thresholds: uncalibrated design values."
        )


class Migration(migrations.Migration):
    dependencies = [("alerts", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, REVERSE), migrations.RunPython(seed_default, migrations.RunPython.noop)]
