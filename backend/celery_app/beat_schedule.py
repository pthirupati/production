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
    "process-subscription-expiry-daily": {
        "task": "celery_app.tasks.process_subscription_expiry",
        "schedule": crontab(hour=6, minute=0),  # 6:00 AM UTC daily
    },
    "marketing-nurture-emails-daily": {
        "task": "celery_app.tasks.send_marketing_nurture_emails",
        "schedule": crontab(hour=10, minute=0),  # 10:00 AM UTC daily (5-day cadence per user)
    },
    "inactive-account-cleanup-daily": {
        "task": "celery_app.tasks.process_inactive_accounts",
        "schedule": crontab(hour=5, minute=0),  # 5:00 AM UTC daily
    },
}

