from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adminpanel", "0003_platformsettings_theme_colors"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="changelog",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Platform changelog entries shown on About page",
            ),
        ),
    ]
