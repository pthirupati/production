from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0006_couponcode_usercertificate"),
    ]

    operations = [
        migrations.AddField(
            model_name="technologysubscription",
            name="payment_method",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
