from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Liveness heartbeat (audit Z5-15). The container healthcheck reads the file
    # this writes; if beat stops scheduling, the file goes stale and the check
    # fails. Every minute, because the heartbeat is the one task whose whole value
    # is telling you quickly that the others have stopped.
    "beat-heartbeat-every-minute": {
        "task": "celery_app.tasks.beat_heartbeat",
        "schedule": crontab(minute="*"),
    },
    "cleanup-expired-labs-every-5-mins": {
        "task": "celery_app.tasks.cleanup_expired_labs",
        "schedule": crontab(minute="*/5"),
    },
    "cleanup-orphaned-containers-hourly": {
        "task": "celery_app.tasks.cleanup_orphaned_containers",
        "schedule": crontab(minute=0),
    },
    # Docker disk reclaim (audit Z5-11). Daily rather than hourly: pruning is I/O
    # heavy and the artifacts it removes accumulate over days, not minutes. 03:10
    # UTC sits in the quiet window ahead of the 04:30 retention sweep.
    "prune-docker-artifacts": {
        "task": "celery_app.tasks.prune_docker_artifacts",
        "schedule": crontab(hour=3, minute=10),
    },
    # Leaderboard snapshot: DAILY, not hourly (audit Z3-7).
    #
    # `LeaderboardEntry` is a cache nobody currently reads — the live endpoint
    # (public_api.views.LeaderboardView) aggregates from UserScenarioProgress
    # directly. Recomputing it hourly meant a full delete + re-insert of every
    # ranked user, 24x a day, for a table with no readers: pure write
    # amplification and dead tuples for autovacuum to chase.
    #
    # Kept rather than removed because the snapshot is the intended path for
    # scaling this endpoint, and a schedule that exists (and is now atomic) is
    # easier to raise than one someone has to rediscover. Raise the frequency when
    # something actually reads it.
    "recalculate-leaderboard-daily": {
        "task": "celery_app.tasks.recalculate_leaderboard",
        "schedule": crontab(hour=5, minute=30),
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
    "fail-stuck-payment-transactions": {
        "task": "billing.fail_stuck_payment_transactions",
        "schedule": crontab(minute="*/30"),  # every 30 minutes
    },
    # PRODUCTION_AUDIT OBS-02: business-signal alerting. Evaluates payment-failure
    # spikes, stale backup heartbeat (dead-man's-switch), deep Celery queues, and
    # login-failure spikes, alerting via common.alerting. This is a NO-OP for
    # alerting until ALERT_WEBHOOK_URL / ALERT_EMAIL are configured (it only logs),
    # so the default deploy is behaviour-unchanged. Interval matches the
    # ALERT_MONITOR_INTERVAL_MINUTES setting default (5 min).
    "monitor-business-signals-every-5-mins": {
        "task": "monitoring.check_business_signals",
        "schedule": crontab(minute="*/5"),
    },
    # Data retention for the sensitive classes — interview messages, async video,
    # resumes, CommandHistory (audit Z4-2). Every RETENTION_*_DAYS defaults to 0,
    # which means REPORT ONLY: this logs what it would purge so the period is
    # chosen against real volumes, and deletes nothing until a period is set.
    "purge-expired-personal-data-daily": {
        "task": "celery_app.tasks.purge_expired_personal_data",
        "schedule": crontab(hour=4, minute=30),  # 4:30 AM UTC, after the other sweeps
    },
}

