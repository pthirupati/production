from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0008_add_subscription_expires_index"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="paymenttransaction",
            index=models.Index(fields=["gateway_order_id"], name="billing_pay_gateway_order_idx"),
        ),
    ]
