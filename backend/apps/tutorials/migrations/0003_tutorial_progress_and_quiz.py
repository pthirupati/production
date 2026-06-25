from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tutorials', '0002_tutorial_course_hierarchy'),
    ]

    operations = [
        migrations.AddField(
            model_name='tutorialsection',
            name='quiz_json',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name='TutorialProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completed_sections', models.JSONField(blank=True, default=list)),
                ('last_section_order', models.PositiveIntegerField(default=0)),
                ('completed', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tutorial', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_progress', to='tutorials.tutorial')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tutorial_progress', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['user', '-updated_at'], name='tutorials_t_user_id_6a8f0d_idx'),
                    models.Index(fields=['user', 'completed'], name='tutorials_t_user_id_9c2b1e_idx'),
                ],
                'unique_together': {('user', 'tutorial')},
            },
        ),
    ]
