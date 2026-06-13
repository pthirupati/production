from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PlatformSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("primary_email", models.EmailField(blank=True, default="", max_length=254)),
                ("payment_email", models.EmailField(blank=True, default="", max_length=254)),
                ("support_email", models.EmailField(blank=True, default="", max_length=254)),
                ("admin_display_currency", models.CharField(default="INR", max_length=3)),
                ("maintenance_enabled", models.BooleanField(default=False)),
                ("maintenance_message", models.TextField(blank=True, default="")),
                ("maintenance_banner_image", models.URLField(blank=True, default="")),
                ("maintenance_banner_style", models.JSONField(blank=True, default=dict)),
                ("maintenance_scheduled_start", models.DateTimeField(blank=True, null=True)),
                ("maintenance_scheduled_end", models.DateTimeField(blank=True, null=True)),
                ("maintenance_notify_users", models.BooleanField(default=True)),
                ("promo_banners", models.JSONField(blank=True, default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Platform settings",
                "verbose_name_plural": "Platform settings",
            },
        ),
    ]
