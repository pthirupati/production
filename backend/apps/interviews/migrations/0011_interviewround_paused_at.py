# Interview round timer pause

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interviews", "0010_interviewanswercorpus"),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewround",
            name="paused_at",
            field=models.DateTimeField(blank=True, help_text="When set, the round timer is frozen until resume.", null=True),
        ),
    ]
