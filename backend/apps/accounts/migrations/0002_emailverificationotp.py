# Generated manually for EmailVerificationOTP model

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailVerificationOTP",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254, db_index=True)),
                ("code", models.CharField(max_length=6)),
                ("session_token", models.CharField(max_length=128, unique=True, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("verified", models.BooleanField(default=False)),
                ("attempts", models.IntegerField(default=0)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
