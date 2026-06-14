from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_notificationpreference"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationpreference",
            name="email_lab_completed",
            field=models.BooleanField(default=False, help_text="Email when completing a lab"),
        ),
        migrations.AlterField(
            model_name="notificationpreference",
            name="email_lab_expired",
            field=models.BooleanField(default=False, help_text="Email when a lab session expires"),
        ),
    ]
