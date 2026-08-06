"""Store email-verification OTPs hashed instead of in plaintext (audit Z4-11).

Deliberately a DROP + ADD rather than a RenameField. A rename would carry the
existing plaintext six-digit codes into `code_hash`, leaving live credentials in the
database under a new name and defeating the point of the change.

Unverified rows are deleted first so anyone mid-signup gets the clear "Invalid
session. Please request a new OTP." rather than a puzzling "Invalid OTP code" from
comparing their code against an empty hash. OTPs live ~10 minutes, so the blast
radius is whoever is on the verify screen at deploy time.
"""
from django.db import migrations, models


def drop_inflight_otps(apps, schema_editor):
    """Codes are about to become unverifiable — clear them rather than strand them."""
    OTP = apps.get_model("accounts", "EmailVerificationOTP")
    OTP.objects.filter(verified=False).delete()


def noop(apps, schema_editor):
    """Reverse leaves the table empty; nothing to restore (the plaintext is gone)."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_organization_webhook_branding"),
    ]

    operations = [
        migrations.RunPython(drop_inflight_otps, noop),
        migrations.RemoveField(
            model_name="emailverificationotp",
            name="code",
        ),
        migrations.AddField(
            model_name="emailverificationotp",
            name="code_hash",
            field=models.CharField(default="", max_length=128),
            preserve_default=False,
        ),
    ]
