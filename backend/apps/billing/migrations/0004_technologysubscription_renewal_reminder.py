from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0003_paymenttransaction"),
    ]

    operations = [
        migrations.AddField(
            model_name="technologysubscription",
            name="renewal_reminder_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
