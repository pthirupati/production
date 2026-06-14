import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adminpanel", "0004_platformsettings_changelog"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlogPost",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("title", models.CharField(max_length=300)),
                ("excerpt", models.TextField(blank=True, default="")),
                ("content", models.TextField(help_text="Markdown or plain text body")),
                ("author_name", models.CharField(blank=True, default="FixitLab Team", max_length=120)),
                ("category", models.CharField(blank=True, default="Product", max_length=80)),
                ("read_minutes", models.PositiveIntegerField(default=5)),
                ("is_published", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-published_at", "-created_at"],
            },
        ),
    ]
