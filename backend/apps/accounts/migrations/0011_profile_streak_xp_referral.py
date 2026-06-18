import random
import string

import django.db.models.deletion
from django.db import migrations, models


def generate_referral_codes(apps, schema_editor):
    """Generate unique 8-char referral codes for all existing profiles."""
    Profile = apps.get_model('accounts', 'Profile')
    existing_codes = set(
        Profile.objects.exclude(referral_code='').values_list('referral_code', flat=True)
    )
    bulk_updates = []
    for profile in Profile.objects.filter(referral_code='').order_by('id'):
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if code not in existing_codes:
                existing_codes.add(code)
                profile.referral_code = code
                bulk_updates.append(profile)
                break
    if bulk_updates:
        Profile.objects.bulk_update(bulk_updates, ['referral_code'], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_profile_support_bot_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='daily_streak',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='profile',
            name='longest_streak',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='profile',
            name='xp',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='profile',
            name='last_activity_date',
            field=models.DateField(blank=True, null=True),
        ),
        # Add without unique constraint first — existing rows all get '' otherwise,
        # which would violate the unique index.
        migrations.AddField(
            model_name='profile',
            name='referral_code',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='profile',
            name='referred_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='referrals',
                to='accounts.profile',
            ),
        ),
        # Populate unique codes for pre-existing profiles before adding the constraint.
        migrations.RunPython(generate_referral_codes, migrations.RunPython.noop),
        # Now safe to add the unique constraint — all rows have distinct codes.
        migrations.AlterField(
            model_name='profile',
            name='referral_code',
            field=models.CharField(blank=True, default='', max_length=20, unique=True),
        ),
    ]
