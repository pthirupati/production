from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_alter_emaillog_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emaillog",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
    ]
