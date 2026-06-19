from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0010_labsession_extensions_metadata"),
    ]

    operations = [
        migrations.AlterField(
            model_name="labsession",
            name="expires_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Computed: started_at + duration_limit seconds.",
                null=True,
            ),
        ),
    ]
