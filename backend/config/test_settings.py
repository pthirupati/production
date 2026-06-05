"""
Test-specific Django settings.
Uses SQLite in-memory so tests can run without Postgres/Redis/RabbitMQ.
"""
import os

# ── Set all required env vars BEFORE importing base settings ──
_test_env = {
    "DJANGO_SECRET_KEY": "test-secret-key-not-for-production-use-1234567890abcdef",
    "DJANGO_DEBUG": "True",
    "DJANGO_ALLOWED_HOSTS": "*",
    "POSTGRES_DB": "test_fixitlab",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "CELERY_BROKER_URL": "memory://",
    "CELERY_RESULT_BACKEND": "cache+memory://",
    "EMAIL_HOST": "localhost",
    "EMAIL_HOST_USER": "",
    "EMAIL_HOST_PASSWORD": "",
    "FRONTEND_URL": "http://localhost:5173",
}
for k, v in _test_env.items():
    os.environ.setdefault(k, v)

from .settings import *  # noqa

# ── Override database to SQLite for fast, isolated tests ──
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ── Disable Celery during tests (run tasks synchronously) ──
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ── Use console email backend ──
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ── Disable throttling so tests don't get rate-limited ──
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}  # noqa: F405

# Monkey-patch AuthRateThrottle to never throttle during tests
from rest_framework.throttling import SimpleRateThrottle
SimpleRateThrottle.allow_request = lambda self, request, view: True

# ── Speed up password hashing for tests ──
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ── Disable channels/redis layer ──
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# ── Disable audit middleware for cleaner test output ──
MIDDLEWARE = [m for m in MIDDLEWARE if "AuditMiddleware" not in m]  # noqa: F405

# ── Caches ──
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Simple logging for tests — avoids JSONFormatter loading Django models too early
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}
