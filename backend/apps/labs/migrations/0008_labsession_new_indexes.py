from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0007_labsession_expires_at"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="labsession",
            index=models.Index(fields=["user", "started_at"], name="labs_labses_user_started_idx"),
        ),
        migrations.AddIndex(
            model_name="labsession",
            index=models.Index(fields=["instance_id"], name="labs_labses_instance_idx"),
        ),
        migrations.AddIndex(
            model_name="labsession",
            index=models.Index(fields=["container_id"], name="labs_labses_container_idx"),
        ),
        migrations.AddIndex(
            model_name="labsession",
            index=models.Index(fields=["status", "expires_at"], name="labs_labses_status_expires_idx"),
        ),
    ]
