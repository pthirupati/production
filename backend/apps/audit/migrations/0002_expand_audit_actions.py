from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("login", "Login"),
                    ("login_failed", "Login Failed"),
                    ("logout", "Logout"),
                    ("lab_start", "Lab Start"),
                    ("lab_stop", "Lab Stop"),
                    ("lab_reset", "Lab Reset"),
                    ("validate", "Validation"),
                    ("admin_action", "Admin Action"),
                    ("payment_failed", "Payment Failed"),
                    ("security_alert", "Security Alert"),
                    ("error", "Error"),
                ],
                max_length=50,
            ),
        ),
    ]
