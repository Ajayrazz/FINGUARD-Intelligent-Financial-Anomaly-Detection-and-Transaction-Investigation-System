from django.db import migrations

FORWARD = """
CREATE FUNCTION risk_assessment_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'risk_engine_riskassessment is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER risk_assessment_no_update_delete
BEFORE UPDATE OR DELETE ON risk_engine_riskassessment
FOR EACH ROW EXECUTE FUNCTION risk_assessment_immutable();
"""
REVERSE = """
DROP TRIGGER risk_assessment_no_update_delete ON risk_engine_riskassessment;
DROP FUNCTION risk_assessment_immutable();
"""


def seed_default(apps, schema_editor):
    RiskConfig = apps.get_model("risk_engine", "RiskConfig")
    if not RiskConfig.objects.exists():
        RiskConfig.objects.create(
            version=1, weights={"A": 0.25, "B": 0.20, "G": 0.20, "F": 0.15, "D": 0.10, "H": 0.10},
            thresholds={"medium": 30.0, "high": 60.0, "critical": 80.0}, missing_signal_policy="renormalize", min_coverage=0.5,
            is_active=True, source="default", notes="Initial weights from docs/08; uncalibrated design values.",
        )  # fmt: skip


class Migration(migrations.Migration):
    dependencies = [("risk_engine", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, REVERSE), migrations.RunPython(seed_default, migrations.RunPython.noop)]
