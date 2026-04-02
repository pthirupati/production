from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-labs-every-5-mins": {
        "task": "celery_app.tasks.cleanup_expired_labs",
        "schedule": crontab(minute="*/5"),
    },
    "cleanup-orphaned-containers-hourly": {
        "task": "celery_app.tasks.cleanup_orphaned_containers",
        "schedule": crontab(minute=0),
    },
    "recalculate-leaderboard-hourly": {
        "task": "celery_app.tasks.recalculate_leaderboard",
        "schedule": crontab(minute=30),
    },
    "cleanup-expired-otps-daily": {
        "task": "celery_app.tasks.cleanup_expired_otps",
        "schedule": crontab(hour=3, minute=0),  # 3:00 AM UTC
    },
    "cleanup-expired-tokens-daily": {
        "task": "celery_app.tasks.cleanup_expired_tokens",
        "schedule": crontab(hour=3, minute=10),  # 3:10 AM UTC
    },
    "cleanup-old-audit-logs-weekly": {
        "task": "celery_app.tasks.cleanup_old_audit_logs",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),  # Sunday 4:00 AM UTC
    },
    "cleanup-old-notifications-weekly": {
        "task": "celery_app.tasks.cleanup_old_notifications",
        "schedule": crontab(hour=4, minute=15, day_of_week=0),  # Sunday 4:15 AM UTC
    },
}

