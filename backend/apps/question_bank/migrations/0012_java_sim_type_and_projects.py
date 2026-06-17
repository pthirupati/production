"""Add Java simulation type to Scenario and create Project/ProjectTask/UserProjectProgress/UserTaskProgress models."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0011_add_scenario_performance_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add java to simulation_type choices
        migrations.AlterField(
            model_name="scenario",
            name="simulation_type",
            field=models.CharField(
                choices=[
                    ("generic", "Normal Simulation (full RHEL)"),
                    ("rhel", "RHEL Linux Simulation"),
                    ("kubernetes", "Kubernetes Simulation"),
                    ("gpu", "GPU / NVIDIA Simulation"),
                    ("baremetal", "Bare Metal / IPMI / VMware"),
                    ("database", "Database Simulation"),
                    ("ansible", "Ansible Simulation"),
                    ("python", "Python Simulation"),
                    ("java", "Java Development Simulation"),
                ],
                default="generic",
                help_text="Technology persona when lab_mode=simulation (one unified engine)",
                max_length=20,
            ),
        ),
        # Project model
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, unique=True)),
                ("architecture_type", models.CharField(
                    choices=[
                        ("2tier", "2-Tier Architecture (Web + DB)"),
                        ("3tier", "3-Tier Architecture (LB + App + DB)"),
                        ("microservices", "Microservices"),
                        ("cicd", "CI/CD Pipeline"),
                        ("custom", "Custom"),
                    ],
                    default="custom",
                    max_length=20,
                )),
                ("description", models.TextField()),
                ("objectives", models.JSONField(blank=True, default=list)),
                ("difficulty", models.CharField(
                    choices=[
                        ("beginner", "Beginner"),
                        ("intermediate", "Intermediate"),
                        ("advanced", "Advanced"),
                    ],
                    default="intermediate",
                    max_length=20,
                )),
                ("estimated_hours", models.PositiveIntegerField(default=4)),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("technology", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="projects",
                    to="question_bank.technology",
                )),
            ],
            options={"ordering": ["order", "title"]},
        ),
        # ProjectTask model
        migrations.CreateModel(
            name="ProjectTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("jira_key", models.CharField(help_text="e.g. PROJ-1", max_length=20)),
                ("description", models.TextField()),
                ("acceptance_criteria", models.TextField(blank=True)),
                ("hint", models.TextField(blank=True, help_text="Jira bot hint when user asks for help")),
                ("order", models.PositiveIntegerField(default=0)),
                ("project", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="tasks",
                    to="question_bank.project",
                )),
                ("depends_on", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="dependents",
                    to="question_bank.projecttask",
                )),
            ],
            options={"ordering": ["order"], "unique_together": {("project", "jira_key")}},
        ),
        # UserProjectProgress model
        migrations.CreateModel(
            name="UserProjectProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(
                    choices=[("in_progress", "In Progress"), ("completed", "Completed")],
                    default="in_progress",
                    max_length=20,
                )),
                ("project", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="user_progress",
                    to="question_bank.project",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="project_progress",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-started_at"], "unique_together": {("user", "project")}},
        ),
        # UserTaskProgress model
        migrations.CreateModel(
            name="UserTaskProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(
                    choices=[("todo", "To Do"), ("in_progress", "In Progress"), ("done", "Done")],
                    default="todo",
                    max_length=20,
                )),
                ("screenshot", models.ImageField(blank=True, null=True, upload_to="project_screenshots/%Y/%m/")),
                ("notes", models.TextField(blank=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("task", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="user_progress",
                    to="question_bank.projecttask",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="task_progress",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["task__order"], "unique_together": {("user", "task")}},
        ),
    ]
