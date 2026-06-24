from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tutorials", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tutorial",
            name="course_slug",
            field=models.SlugField(blank=True, db_index=True, max_length=120),
        ),
        migrations.AddField(
            model_name="tutorial",
            name="course_title",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="tutorial",
            name="module_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="tutorial",
            name="level_track",
            field=models.CharField(
                blank=True,
                choices=[
                    ("beginner", "Beginner"),
                    ("intermediate", "Intermediate"),
                    ("advanced", "Advanced"),
                    ("expert", "Expert"),
                    ("enterprise", "Enterprise"),
                ],
                db_index=True,
                default="beginner",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="tutorial",
            index=models.Index(fields=["course_slug", "module_order"]),
        ),
    ]
