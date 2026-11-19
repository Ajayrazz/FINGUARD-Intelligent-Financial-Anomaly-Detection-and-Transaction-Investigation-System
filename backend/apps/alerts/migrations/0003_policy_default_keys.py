from django.db import migrations


def add_missing_keys(apps, schema_editor):
    """Policy v1 was seeded before `max_alerts_per_rule` and `auto_case` existed; add the defaults so it can be copied."""
    AlertPolicy = apps.get_model("alerts", "AlertPolicy")
    for pol in AlertPolicy.objects.all():
        cfg = dict(pol.config)
        cfg.setdefault("max_alerts_per_rule", 500)
        cfg.setdefault("auto_case", {"enabled": True, "min_severity": "critical"})
        if cfg != pol.config:
            AlertPolicy.objects.filter(pk=pol.pk).update(config=cfg)


class Migration(migrations.Migration):
    dependencies = [("alerts", "0002_append_only_events_and_default_policy")]
    operations = [migrations.RunPython(add_missing_keys, migrations.RunPython.noop)]
