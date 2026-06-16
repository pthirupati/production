from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_expand_audit_actions"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="auditlog",
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["user", "-created_at"], name="audit_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["action", "-created_at"], name="audit_action_created_idx"),
        ),
    ]
