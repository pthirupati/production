from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0007_technologysubscription_payment_method"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="technologysubscription",
            index=models.Index(fields=["is_active", "expires_at"], name="techsub_active_expires_idx"),
        ),
    ]
