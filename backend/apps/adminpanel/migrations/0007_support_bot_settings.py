from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adminpanel", "0006_seed_blog_posts"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="support_bot_custom_faq",
            field=models.JSONField(blank=True, default=list, help_text='List of {"keywords": ["disk"], "answer": "..."}'),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="support_bot_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="support_bot_name",
            field=models.CharField(blank=True, default="FixitLab Assistant", max_length=80),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="support_bot_quick_topics",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="support_bot_typing_delay_ms",
            field=models.PositiveIntegerField(default=1200),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="support_bot_welcome_message",
            field=models.TextField(blank=True, default=""),
        ),
    ]
