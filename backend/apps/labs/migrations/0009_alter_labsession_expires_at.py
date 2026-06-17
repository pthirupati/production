from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0008_labsession_new_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="labsession",
            name="expires_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Computed: started_at + duration_limit seconds. Used for efficient expiry filtering.",
                null=True,
            ),
        ),
    ]
