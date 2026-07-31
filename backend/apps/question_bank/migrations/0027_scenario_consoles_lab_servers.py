# Generated manually for Scenario.consoles + Scenario.lab_servers

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0026_scenario_datacenter_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenario",
            name="consoles",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Ordered lab console keys from scenario YAML (e.g. ['azure','terminal']). "
                    "Empty means LabRunner falls back to slug / simulation_type heuristics."
                ),
            ),
        ),
        migrations.AddField(
            model_name="scenario",
            name="lab_servers",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Lab Server declarations from scenario YAML "
                    "[{id, role, hostname, persona, appears_in, ...}]. "
                    "Empty falls back to on-disk YAML or persona defaults at provision time."
                ),
            ),
        ),
    ]
