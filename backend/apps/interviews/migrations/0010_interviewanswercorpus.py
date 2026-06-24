# Generated for admin-uploaded interview answer corpora

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0019_technology_is_free"),
        ("interviews", "0009_interviewround_last_practical_submission"),
    ]

    operations = [
        migrations.CreateModel(
            name="InterviewAnswerCorpus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("raw_text", models.TextField(blank=True, default="")),
                ("entries", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "technology",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interview_answer_corpora",
                        to="question_bank.technology",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Interview answer corpora",
                "ordering": ["-updated_at"],
            },
        ),
    ]
