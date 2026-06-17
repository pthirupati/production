from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0006_marketing_campaign_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emaillog",
            name="id",
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
        ),
    ]
