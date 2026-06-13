from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="labsession",
            name="lab_hosts",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="[{name, role, container_id, ip, ssh_user}] for SSH/SCP/NFS scenarios",
            ),
        ),
    ]
