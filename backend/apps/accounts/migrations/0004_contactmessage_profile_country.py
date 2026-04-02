import uuid
from django.db import migrations, models


def add_country_column_if_missing(apps, schema_editor):
    """Add country column only if it doesn't exist (handles DB already having it)."""
    from django.db import connection
    db_engine = connection.vendor  # 'postgresql', 'sqlite', etc.
    with connection.cursor() as cursor:
        if db_engine == 'postgresql':
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'accounts_profile' AND column_name = 'country'"
            )
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE accounts_profile ADD COLUMN country varchar(100) DEFAULT '' NOT NULL"
                )
        elif db_engine == 'sqlite':
            cursor.execute("PRAGMA table_info(accounts_profile)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'country' not in columns:
                cursor.execute(
                    "ALTER TABLE accounts_profile ADD COLUMN country varchar(100) DEFAULT '' NOT NULL"
                )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_socialaccount'),
    ]

    operations = [
        # Add country field to Profile state + DB (idempotent)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='profile',
                    name='country',
                    field=models.CharField(blank=True, default='', help_text="User's country or location", max_length=100),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_country_column_if_missing, migrations.RunPython.noop),
            ],
        ),
        # Create ContactMessage model
        migrations.CreateModel(
            name='ContactMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('email', models.EmailField(max_length=254)),
                ('subject', models.CharField(max_length=300)),
                ('message', models.TextField(max_length=5000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
