from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('question_bank', '0024_learningjourney_journeystep'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scenario',
            name='simulation_type',
            field=models.CharField(choices=[('generic', 'Normal Simulation (full RHEL)'), ('rhel', 'RHEL Linux Simulation'), ('kubernetes', 'Kubernetes Simulation'), ('gpu', 'GPU / NVIDIA Simulation'), ('baremetal', 'Bare Metal / IPMI / VMware'), ('database', 'Database Simulation'), ('ansible', 'Ansible Simulation'), ('ansible-awx', 'Ansible AWX / Tower Simulation'), ('terraform', 'Terraform / AWS CLI Simulation'), ('python', 'Python Simulation'), ('java', 'Java Development Simulation'), ('commvault', 'Commvault Backup Simulation'), ('netapp', 'NetApp ONTAP Storage Simulation'), ('dellemc', 'Dell EMC Unisphere / PowerMax Simulation'), ('datacenter', 'Physical Datacenter (DCIM) Simulation'), ('soc', 'SOC / SIEM Cybersecurity Simulation')], default='generic', help_text='Technology persona when lab_mode=simulation (one unified engine)', max_length=20),
        ),
    ]
