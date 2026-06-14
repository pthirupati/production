from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adminpanel", "0002_banner_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="theme_colors",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Admin-editable accent colors: cyan, purple, amber, green, etc.",
            ),
        ),
    ]
