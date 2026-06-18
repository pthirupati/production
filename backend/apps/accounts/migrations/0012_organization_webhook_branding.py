from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_profile_streak_xp_referral'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='webhook_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='organization',
            name='webhook_secret',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='organization',
            name='logo_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='organization',
            name='primary_color',
            field=models.CharField(
                blank=True, default='', max_length=7,
                help_text='Hex color, e.g. #6366f1',
            ),
        ),
        migrations.AddField(
            model_name='organization',
            name='custom_domain',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
