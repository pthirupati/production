from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0012_java_sim_type_and_projects"),
    ]

    operations = [
        migrations.AddField(
            model_name="technology",
            name="maintenance_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="technology",
            name="maintenance_message",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="technology",
            name="maintenance_scheduled_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="technology",
            name="maintenance_scheduled_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
