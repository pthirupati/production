from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adminpanel", "0001_platformsettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="promo_banners_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="maintenance_banner_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
