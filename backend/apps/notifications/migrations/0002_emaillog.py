# Generated manually for EmailLog model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(max_length=500)),
                ("to_email", models.EmailField(max_length=254)),
                ("template", models.CharField(max_length=200)),
                ("status", models.CharField(choices=[("sent", "Sent"), ("failed", "Failed")], default="sent", max_length=10)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["-created_at"], name="notificatio_created_4c6dec_idx"),
                    models.Index(fields=["status"], name="notificatio_status_18a272_idx"),
                ],
            },
        ),
    ]
