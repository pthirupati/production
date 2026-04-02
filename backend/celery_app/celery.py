import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("fixitlab")

# Read config from Django settings (CELERY_*)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in all installed apps + celery_app
app.autodiscover_tasks()
app.autodiscover_tasks(["celery_app"])

