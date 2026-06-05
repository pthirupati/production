from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0005_scenario_jira_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenario",
            name="docker_privileged",
            field=models.BooleanField(
                default=False,
                help_text="Run lab container privileged (required for LVM/device scenarios)",
            ),
        ),
        migrations.AlterField(
            model_name="scenario",
            name="infrastructure_type",
            field=models.CharField(
                choices=[
                    ("docker", "Docker Container"),
                    ("aws_ec2", "AWS EC2 Instance"),
                    ("digitalocean", "DigitalOcean Droplet"),
                ],
                default="docker",
                help_text="Where to run this scenario: docker (recommended), aws_ec2, or digitalocean",
                max_length=20,
            ),
        ),
    ]
