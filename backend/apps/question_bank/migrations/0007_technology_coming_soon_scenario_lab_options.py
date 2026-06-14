from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0006_scenario_docker_privileged"),
    ]

    operations = [
        migrations.AddField(
            model_name="technology",
            name="coming_soon",
            field=models.BooleanField(
                default=False,
                help_text="Show as coming soon — visible but not openable until disabled",
            ),
        ),
        migrations.AddField(
            model_name="scenario",
            name="requires_companion_hosts",
            field=models.BooleanField(
                default=False,
                help_text="Provision dual Docker containers (NFS/SCP/SSH/network scenarios)",
            ),
        ),
        migrations.AddField(
            model_name="scenario",
            name="dual_terminal",
            field=models.BooleanField(
                default=False,
                help_text="Show two terminal panels in the lab UI",
            ),
        ),
        migrations.AddField(
            model_name="scenario",
            name="lab_mode",
            field=models.CharField(
                choices=[("docker", "Docker Container"), ("simulation", "Simulation (no real container)")],
                default="docker",
                help_text="Docker container or simulated environment",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="scenario",
            name="simulation_type",
            field=models.CharField(
                choices=[
                    ("none", "None"),
                    ("boot", "Boot / IPMI / GRUB"),
                    ("gpu", "GPU (NVIDIA/AMD)"),
                    ("ansible", "Ansible multi-host"),
                    ("baremetal", "Bare metal"),
                ],
                default="none",
                help_text="Simulation engine when lab_mode=simulation",
                max_length=20,
            ),
        ),
    ]
