from pathlib import Path
import environ
import os
from datetime import timedelta

# --------------------------------------------------
# Base paths & env
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)
_env_root = BASE_DIR.parent
_env_file = _env_root / ".env.production" if (_env_root / ".env.production").exists() else _env_root / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"] if env.bool("DJANGO_DEBUG", default=False) else [],
)

# --------------------------------------------------
# Applications
# --------------------------------------------------
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    "django_celery_results",
    "django_celery_beat",
    "django_filters",

    # API docs
    "drf_spectacular",

    # Local Django apps
    "apps.accounts",
    "apps.question_bank",
    "apps.scenario_versions",
    "apps.hints",
    "apps.labs",
    "apps.terminal",
    "apps.progress",
    "apps.leaderboard",
    "apps.billing",
    "apps.adminpanel",
    "apps.audit",
    "apps.notifications",
    "apps.community",
    "apps.ratings",
    "apps.jira_integration",
    "apps.interviews",
    "apps.support",
]

# --------------------------------------------------
# Middleware
# --------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Security: request metadata extraction and JWT session validation
    "common.middleware_security.RequestMetadataMiddleware",
    "common.middleware_security.AdminIPRestrictionMiddleware",
    "common.middleware_security.JWTSessionValidationMiddleware",
    "common.middleware_security.SecurityHeadersMiddleware",

    # Security: restrict Django admin to superusers only
    "common.middleware.AdminAccessMiddleware",

    # Audit (LAST)
    "apps.audit.middleware.AuditMiddleware",
]

ROOT_URLCONF = "config.urls"

# --------------------------------------------------
# CORS
# --------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:80",
    "http://localhost",
])
CORS_ALLOW_CREDENTIALS = True

# CSRF
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[
    "http://localhost:8080",
    "http://localhost",
    "http://localhost:5173",
])

# --------------------------------------------------
# Templates
# --------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------
# WSGI / ASGI
# --------------------------------------------------
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------
# Database (PostgreSQL – persistent)
# --------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
        "CONN_MAX_AGE": 600,  # 10 min persistent connections (reduces connect overhead)
        "CONN_HEALTH_CHECKS": True,  # Verify connections before reuse
        "OPTIONS": {
            "connect_timeout": 5,
        },
    }
}

# --------------------------------------------------
# Password validation
# --------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------
# Static & Media files
# --------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Serve uploaded files through Django when nginx proxies /media/ to the backend.
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=True)

# Limit upload sizes to prevent DoS via large file uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB

# --------------------------------------------------
# Django REST Framework + JWT
# --------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "auth": "10/minute",  # Strict limit on auth endpoints
        "lab_start": "60/hour",  # Limit lab provisioning (DoS protection)
        "login": "5/minute",
        "otp": "3/minute",
        "password_reset": "3/minute",
        "payment": "20/hour",
        "interview": "100/day",
        "strict_anon": "10/minute",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FixitLab API",
    "DESCRIPTION": "Public REST API for scenarios, labs, billing, and progress.",
    "VERSION": "2.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

SIMPLE_JWT = {
    # SECURITY: Use RS256 (asymmetric) instead of HS256 for higher security
    # RS256 uses a private key to sign and public key to verify
    # This prevents token tampering even if someone intercepts the token
    "ALGORITHM": env("JWT_ALGORITHM", default="RS256"),
    
    # Token lifetimes
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),  # Short-lived access tokens for security
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    
    # RSA Keys (set from environment variables or PEM file paths)
    # Generate with: python common/security.py generate_keys
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=None),
    "VERIFYING_KEY": env("JWT_VERIFYING_KEY", default=None),
    
    # Token management
    "ROTATE_REFRESH_TOKENS": True,  # Issue new refresh token on each refresh
    "BLACKLIST_AFTER_ROTATION": True,  # Invalidate old refresh tokens
    "UPDATE_LAST_LOGIN": True,  # Update user.last_login on each token refresh
    
    # JWT ID for session tracking and revocation
    "JTI_CLAIM": "jti",  # Custom claim for unique token identifier
    "JTI_GENERATION_ENABLED": True,  # EnableJWT ID generation
    
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

def _read_pem_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


if not SIMPLE_JWT["SIGNING_KEY"]:
    SIMPLE_JWT["SIGNING_KEY"] = env("JWT_RSA_PRIVATE_KEY", default=None) or _read_pem_file(
        env("JWT_RSA_PRIVATE_KEY_PATH", default="")
    )
if not SIMPLE_JWT["VERIFYING_KEY"]:
    SIMPLE_JWT["VERIFYING_KEY"] = env("JWT_RSA_PUBLIC_KEY", default=None) or _read_pem_file(
        env("JWT_RSA_PUBLIC_KEY_PATH", default="")
    )

# HS256 fallback when explicitly configured or in debug mode
if not SIMPLE_JWT["SIGNING_KEY"]:
    if SIMPLE_JWT["ALGORITHM"] == "HS256":
        SIMPLE_JWT["SIGNING_KEY"] = env("JWT_HS256_SECRET", default=SECRET_KEY)
    elif DEBUG:
        SIMPLE_JWT["ALGORITHM"] = "HS256"
        SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY
    else:
        import warnings
        warnings.warn(
            "JWT RSA keys not configured in production — set JWT_RSA_PRIVATE_KEY, "
            "JWT_SIGNING_KEY, or JWT_ALGORITHM=HS256",
            stacklevel=1,
        )


# --------------------------------------------------
# Channels (Redis)
# --------------------------------------------------
_channels_redis_host = env("REDIS_HOST", default="redis")
_channels_redis_port = int(env("REDIS_PORT", default="6379"))
_channels_redis_password = env("REDIS_PASSWORD", default="")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": (_channels_redis_host, _channels_redis_port),
                    **({"password": _channels_redis_password} if _channels_redis_password else {}),
                }
            ] if _channels_redis_password else [(_channels_redis_host, _channels_redis_port)],
            "capacity": 1500,  # Max messages per channel before oldest dropped
            "expiry": 60,  # Message expiry in seconds
        },
    }
}

# --------------------------------------------------
# Celery (RabbitMQ)
# --------------------------------------------------
_celery_redis_host = env("REDIS_HOST", default="redis")
_celery_redis_port = env("REDIS_PORT", default="6379")
_celery_redis_password = env("REDIS_PASSWORD", default="")
_celery_redis_auth = f":{_celery_redis_password}@" if _celery_redis_password else ""

CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_BACKEND = f"redis://{_celery_redis_auth}{_celery_redis_host}:{_celery_redis_port}/2"  # Redis (fast) instead of django-db
CELERY_RESULT_EXPIRES = 3600  # Expire results after 1 hour
CELERY_TIMEZONE = "UTC"
CELERY_WORKER_MAX_TASKS_PER_CHILD = 200  # Prevent memory leaks in long-lived workers
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Fair scheduling for long-running tasks
CELERY_TASK_ACKS_LATE = True  # Re-deliver tasks if worker crashes mid-execution

# Task routing: separate queues for long vs short tasks
CELERY_TASK_ROUTES = {
    "celery_app.tasks.provision_cloud_lab": {"queue": "provisioning"},
    "celery_app.tasks.cleanup_expired_labs": {"queue": "maintenance"},
    "celery_app.tasks.cleanup_orphaned_containers": {"queue": "maintenance"},
    "celery_app.tasks.recalculate_leaderboard": {"queue": "maintenance"},
    "apps.notifications.tasks.*": {"queue": "notifications"},
}

# Celery Beat
from celery_app.beat_schedule import CELERY_BEAT_SCHEDULE  # noqa

# --------------------------------------------------
# Email (for notifications)
# --------------------------------------------------
# Priority: SMTP credentials → MailHog (local dev) → Console fallback
_email_user = env("EMAIL_HOST_USER", default="")
_email_host = env("EMAIL_HOST", default="mailhog")

if _email_user:
    # Production: use real SMTP (Mailgun, SES, SendGrid, etc.)
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = _email_host
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_USE_TLS = True
else:
    # Development: use MailHog (SMTP on port 1025, web UI on port 8025)
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "mailhog"
    EMAIL_PORT = 1025
    EMAIL_USE_TLS = False

EMAIL_HOST_USER = _email_user
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="FixitLab <no-reply@fixitlab.com>")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=15)

# Gmail API (HTTPS — use on DigitalOcean where SMTP 587/465 is blocked)
GMAIL_OAUTH_CLIENT_ID = env("GMAIL_OAUTH_CLIENT_ID", default=env("GOOGLE_CLIENT_ID", default=""))
GMAIL_OAUTH_CLIENT_SECRET = env("GMAIL_OAUTH_CLIENT_SECRET", default=env("GOOGLE_CLIENT_SECRET", default=""))
GMAIL_OAUTH_REFRESH_TOKEN = env("GMAIL_OAUTH_REFRESH_TOKEN", default="")

# Optional SendGrid HTTP API (100/day free tier)
SENDGRID_API_KEY = env("SENDGRID_API_KEY", default="")

# Frontend URL for email links
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:8080")
OAUTH_CALLBACK_BASE_URL = env("OAUTH_CALLBACK_BASE_URL", default="")
GITHUB_OAUTH_CALLBACK_URL = env("GITHUB_OAUTH_CALLBACK_URL", default="")
# When true, skip Gmail/SendGrid/SMTP delivery (E2E/CI). OTP still stored in DB.
SKIP_EMAIL_TESTS = env.bool("SKIP_EMAIL_TESTS", default=False)
E2E_TEST_EMAIL_SUFFIXES = ("@fixitlab-test.local",)

# --------------------------------------------------
# Configurable Contact Emails
# --------------------------------------------------
PRIMARY_EMAIL = env("PRIMARY_EMAIL", default="fixitlab@gmail.com")
PAYMENT_EMAIL = env("PAYMENT_EMAIL", default="kubelearn464@gmail.com")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", default="fixitlab.techsupport@gmail.com")

# --------------------------------------------------
# Maintenance Mode
# --------------------------------------------------
MAINTENANCE_MODE = env.bool("MAINTENANCE_MODE", default=False)
MAINTENANCE_MESSAGE = env(
    "MAINTENANCE_MESSAGE",
    default="We are currently performing scheduled maintenance. Please check back soon."
)

# --------------------------------------------------
# Internationalization
# --------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------
# Business Details (invoices, receipts)
# --------------------------------------------------
BUSINESS_NAME = env("BUSINESS_NAME", default="FixitLab")
BUSINESS_ADDRESS = env("BUSINESS_ADDRESS", default="")
BUSINESS_GSTIN = env("BUSINESS_GSTIN", default="")
BUSINESS_PAN = env("BUSINESS_PAN", default="")

# --------------------------------------------------
# Default PK
# --------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------
# Lab / Docker provisioning
# --------------------------------------------------
LAB_PROVIDER = env("LAB_PROVIDER", default="docker")  # docker recommended — no per-user cloud VM cost
LAB_MAX_DURATION_MINUTES = env.int("LAB_MAX_DURATION_MINUTES", default=60)
LAB_CLEANUP_INTERVAL_MINUTES = env.int("LAB_CLEANUP_INTERVAL_MINUTES", default=5)
DOCKER_SOCKET = env("DOCKER_SOCKET", default="unix:///var/run/docker.sock")
DOCKER_NETWORK = env("DOCKER_NETWORK", default="fixitlab_labs")
DOCKER_SCENARIO_IMAGE_PREFIX = env("DOCKER_SCENARIO_IMAGE_PREFIX", default="fixitlab/scenario-")
DOCKER_CONTAINER_MEMORY_LIMIT = env("DOCKER_CONTAINER_MEMORY_LIMIT", default="512m")
DOCKER_CONTAINER_CPU_LIMIT = env.float("DOCKER_CONTAINER_CPU_LIMIT", default=1.0)

# AWS provisioning (for later)
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_REGION = env("AWS_REGION", default="us-east-1")
AWS_LAB_BASE_AMI = env("AWS_LAB_BASE_AMI", default="ami-0c7217cdde317cfec")
AWS_LAB_AMI_PREFIX = env("AWS_LAB_AMI_PREFIX", default="fixitlab-scenario-")
AWS_LAB_INSTANCE_TYPE = env("AWS_LAB_INSTANCE_TYPE", default="t3.micro")
AWS_LAB_SUBNET_ID = env("AWS_LAB_SUBNET_ID", default="")
AWS_LAB_SECURITY_GROUP_ID = env("AWS_LAB_SECURITY_GROUP_ID", default="")
AWS_LAB_KEY_PAIR = env("AWS_LAB_KEY_PAIR", default="fixitlab-labs")
AWS_LAB_KEY_PEM = env("AWS_LAB_KEY_PEM", default="")
AWS_LAB_KEY_PATH = env("AWS_LAB_KEY_PATH", default="")

# DigitalOcean provisioning
DO_API_TOKEN = env("DO_API_TOKEN", default="")
DO_SSH_KEY_ID = env("DO_SSH_KEY_ID", default="")
DO_SSH_KEY_PEM = env("DO_SSH_KEY_PEM", default="")
DO_SSH_KEY_PATH = env("DO_SSH_KEY_PATH", default="")
DO_REGION = env("DO_REGION", default="nyc1")
DO_SIZE = env("DO_SIZE", default="s-1vcpu-1gb")

# --------------------------------------------------
# AI Interview Studio (100% free — browser voice + rule-based AI)
# --------------------------------------------------
INTERVIEW_ENABLED = env.bool("INTERVIEW_ENABLED", default=True)
INTERVIEW_VOICE_ENGINE = env("INTERVIEW_VOICE_ENGINE", default="browser")
INTERVIEW_AV_GRACE_SECONDS = env.int("INTERVIEW_AV_GRACE_SECONDS", default=300)
INTERVIEW_ROUND_SCHEDULE_HOURS = env.int("INTERVIEW_ROUND_SCHEDULE_HOURS", default=48)
INTERVIEW_STAFF_FREE_BY_DEFAULT = env.bool("INTERVIEW_STAFF_FREE_BY_DEFAULT", default=True)
INTERVIEW_ALLOW_ADMIN_OBSERVER = env.bool("INTERVIEW_ALLOW_ADMIN_OBSERVER", default=True)
INTERVIEW_FREE_CAMPAIGNS_PER_MONTH = env.int("INTERVIEW_FREE_CAMPAIGNS_PER_MONTH", default=1)

# Marketing nurture emails (sample → subscribe, no-sub → technology benefits)
MARKETING_EMAILS_ENABLED = env.bool("MARKETING_EMAILS_ENABLED", default=True)
MARKETING_NUDGE_INTERVAL_DAYS = env.int("MARKETING_NUDGE_INTERVAL_DAYS", default=5)
MARKETING_MIN_ACCOUNT_AGE_DAYS = env.int("MARKETING_MIN_ACCOUNT_AGE_DAYS", default=3)
MARKETING_INACTIVE_LOGIN_DAYS = env.int("MARKETING_INACTIVE_LOGIN_DAYS", default=120)
JIRA_TEAM_REPLY_DELAY_SECONDS = env.int("JIRA_TEAM_REPLY_DELAY_SECONDS", default=30)

# Inactive account cleanup (no subscription within N months)
INACTIVE_ACCOUNT_CLEANUP_ENABLED = env.bool("INACTIVE_ACCOUNT_CLEANUP_ENABLED", default=True)
INACTIVE_ACCOUNT_MONTHS = env.int("INACTIVE_ACCOUNT_MONTHS", default=3)
INACTIVE_ACCOUNT_WARNING_DAYS = env.int("INACTIVE_ACCOUNT_WARNING_DAYS", default=14)

# --------------------------------------------------
# Jira Cloud integration
# --------------------------------------------------
JIRA_ENABLED = env.bool("JIRA_ENABLED", default=False)
JIRA_BASE_URL = env("JIRA_BASE_URL", default="")
JIRA_EMAIL = env("JIRA_EMAIL", default="")
JIRA_API_TOKEN = env("JIRA_API_TOKEN", default="")
JIRA_PROJECT_KEY = env("JIRA_PROJECT_KEY", default="FIXIT")
JIRA_ISSUE_TYPE = env("JIRA_ISSUE_TYPE", default="Task")
JIRA_TRANSITION_IN_PROGRESS = env("JIRA_TRANSITION_IN_PROGRESS", default="In Progress")
JIRA_TRANSITION_TODO = env("JIRA_TRANSITION_TODO", default="To Do")
JIRA_TRANSITION_DONE = env("JIRA_TRANSITION_DONE", default="Done")
JIRA_WEBHOOK_SECRET = env("JIRA_WEBHOOK_SECRET", default="")
# In-app Jira simulation (no Atlassian dependency). Set false to use real Jira Cloud API.
JIRA_SIMULATION_MODE = env.bool("JIRA_SIMULATION_MODE", default=True)
JIRA_SIMULATION_PREFIX = env("JIRA_SIMULATION_PREFIX", default="KAN")

# Comma-separated IPs allowed to access /django-admin/ and /api/admin/
# Empty = allow all (set in production to your office/VPN IP)
ADMIN_ALLOWED_IPS = [ip.strip() for ip in env("ADMIN_ALLOWED_IPS", default="").split(",") if ip.strip()]

# --------------------------------------------------
# Social OAuth (GitHub + Google)
# --------------------------------------------------
GITHUB_CLIENT_ID = env("GITHUB_CLIENT_ID", default="")
GITHUB_CLIENT_SECRET = env("GITHUB_CLIENT_SECRET", default="")
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")

# --------------------------------------------------
# Stripe billing
# --------------------------------------------------
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_PRO_PRICE_ID = env("STRIPE_PRO_PRICE_ID", default="")
STRIPE_TEAM_PRICE_ID = env("STRIPE_TEAM_PRICE_ID", default="")
SITE_URL = env("SITE_URL", default="http://localhost:8080")

# --------------------------------------------------
# Razorpay (technology subscriptions)
# --------------------------------------------------
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")
# Demo payments only when explicitly enabled (local dev); never default on in production
DEMO_PAYMENT_ENABLED = env.bool("DEMO_PAYMENT_ENABLED", default=False)

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
            environment="production" if not DEBUG else "development",
        )
    except ImportError:
        pass

# --------------------------------------------------
# Currency Settings
# --------------------------------------------------
DEFAULT_CURRENCY = env("DEFAULT_CURRENCY", default="INR")
ENABLE_CURRENCY_CONVERSION = env.bool("ENABLE_CURRENCY_CONVERSION", default=True)

# --------------------------------------------------
# Redis caching
# --------------------------------------------------
_redis_password = env("REDIS_PASSWORD", default="")
_redis_auth = f":{_redis_password}@" if _redis_password else ""
_redis_host = env("REDIS_HOST", default="redis")
_redis_port = env("REDIS_PORT", default="6379")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{_redis_auth}{_redis_host}:{_redis_port}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# --------------------------------------------------
# Security (all environments)
# --------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 3600 * 8  # 8 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Password hashing — Argon2 preferred
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# --------------------------------------------------
# Security (production only)
# --------------------------------------------------
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Internal Docker/k8s probes hit Daphne over HTTP — must not 301 to HTTPS
    SECURE_REDIRECT_EXEMPT = [r"^api/health/?$"]

# --------------------------------------------------
# Logging (structured JSON with PII masking)
# --------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        # Structured JSON format with PII masking
        "json": {
            "()": "common.logging_utils.JSONFormatter",
        },
        # Fallback verbose format for local development
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        # Console handler for Docker logs
        "console_json": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "level": "INFO",
        },
        # Console handler for development
        "console_verbose": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": "DEBUG",
        },
    },
    "root": {
        "handlers": ["console_json"] if not DEBUG else ["console_verbose"],
        "level": "INFO",
    },
    "loggers": {
        # Django core loggers
        "django": {
            "handlers": ["console_json"] if not DEBUG else ["console_verbose"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console_json"] if not DEBUG else ["console_verbose"],
            "level": "INFO",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console_json"] if not DEBUG else ["console_verbose"],
            "level": "INFO",
            "propagate": False,
        },
        
        # App loggers
        "apps": {
            "handlers": ["console_json"] if not DEBUG else ["console_verbose"],
            "level": "INFO",
            "propagate": False,
        },
        
        # Security-related loggers
        "common.security": {
            "handlers": ["console_json"] if not DEBUG else ["console_verbose"],
            "level": "INFO",
            "propagate": False,
        },
        "common.middleware_security": {
            "handlers": ["console_json"] if not DEBUG else ["console_verbose"],
            "level": "INFO",
            "propagate": False,
        },
        
        # Celery loggers
        "celery": {
            "handlers": ["console_json"] if not DEBUG else ["console_verbose"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

