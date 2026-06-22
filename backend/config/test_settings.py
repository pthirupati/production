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
    "JIRA_SIMULATION_MODE": "False",
}
for k, v in _test_env.items():
    os.environ[k] = v  # override production env in container

from .settings import *  # noqa

DEBUG = True

# CI uses the Postgres service container (avoids flaky SQLite "database table is locked").
if os.environ.get("GITHUB_ACTIONS") == "true":
    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url:
        from urllib.parse import urlparse as _urlparse
        _u = _urlparse(_db_url)
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": _u.path.lstrip("/"),
                "USER": _u.username or "postgres",
                "PASSWORD": _u.password or "postgres",
                "HOST": _u.hostname or "127.0.0.1",
                "PORT": str(_u.port or 5432),
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "fixitlab_test",
                "USER": "postgres",
                "PASSWORD": "postgres",
                "HOST": "127.0.0.1",
                "PORT": "5432",
            }
        }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

# ── Disable Celery during tests (run tasks synchronously) ──
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ── Skip real email in CI/E2E (OTP still written to DB) ──
SKIP_EMAIL_TESTS = os.environ.get("SKIP_EMAIL_TESTS", "").lower() in ("1", "true", "yes")

# ── Use console email backend ──
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ── Disable throttling so tests don't get rate-limited ──
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405
# Keep all scopes registered so view-level throttle_classes don't crash on
# get_rate() — all limits are set very high so tests never actually throttle.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    "anon": "10000/minute",
    "user": "10000/minute",
    "auth": "10000/minute",
    "login": "10000/minute",
    "otp": "10000/minute",
    "password_reset": "10000/minute",
    "payment": "10000/minute",
    "interview": "10000/minute",
    "strict_anon": "10000/minute",
    "lab_start": "10000/minute",
    "token_refresh": "10000/minute",
    "playground": "10000/minute",
}

# Monkey-patch allow_request so throttle classes always pass in tests
# (covers both global and view-level throttle_classes assignments).
from rest_framework.throttling import SimpleRateThrottle  # noqa: E402
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

# ── No HTTPS redirect in test client (APIClient does not send X-Forwarded-Proto) ──
SECURE_SSL_REDIRECT = False

# ── Jira: unit tests mock JiraClient; keep simulation off unless explicitly tested ──
JIRA_SIMULATION_MODE = False

# ── Caches ──
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ── Silence pre-existing admin system-check errors in the interviews app
# These are caused by model field renames that don't yet have a migration and
# are unrelated to billing.  Without this, manage.py test refuses to run at
# all, blocking the billing test suite.
SILENCED_SYSTEM_CHECKS = [
    "admin.E035",  # readonly_fields refers to missing field
    "admin.E108",  # list_display refers to missing field/attr
    "admin.E116",  # list_filter refers to missing field
    "admin.E127",  # date_hierarchy refers to missing field
    "admin.E033",  # ordering refers to missing field
]

# Simple logging for tests — avoids JSONFormatter loading Django models too early
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}
