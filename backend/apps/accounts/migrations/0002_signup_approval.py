from django.db import migrations, models


def verify_existing(apps, schema_editor):
    """Everyone who exists before self-registration was created by an administrator: treat as verified and approved."""
    User = apps.get_model("accounts", "User")
    User.objects.filter(email_verified_at__isnull=True).update(email_verified_at=models.F("created_at"))


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AddField("user", "email_verified_at", models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            "user",
            "approval_status",
            models.CharField(
                choices=[("approved", "Approved"), ("pending", "Pending"), ("rejected", "Rejected")],
                default="approved",
                max_length=10,
            ),
        ),
        migrations.RunPython(verify_existing, migrations.RunPython.noop),
    ]
