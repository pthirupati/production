from pathlib import Path
import environ
import os
import socket
from datetime import timedelta
from decimal import Decimal

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

# Vault — inject KV secrets into os.environ before any env() calls
# No-op when VAULT_ENABLED is not set; graceful fallback if Vault unreachable.
from config.vault_loader import load_vault_secrets  # noqa: E402
load_vault_secrets()

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
    "apps.vmware_sim",
    "apps.itsm",
    "apps.tutorials",
    "apps.certifications",
]

# --------------------------------------------------
# Middleware
# --------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
# Serve uploaded files through Django only in DEBUG or when explicitly enabled.
# Production should serve /media/ from nginx with auth, not via Django.
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=DEBUG)

# Limit upload sizes to prevent DoS via large file uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB

# --------------------------------------------------
# Django REST Framework + JWT
# --------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # Cookie-based JWT must come first so httpOnly cookies are honoured;
        # it falls back to Authorization header internally.
        "apps.auth_app.cookie_auth.CookieJWTAuthentication",
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
    # Throttle rates — tuned for MANY concurrent users, including users sharing a
    # single egress IP (corporate NAT / VPN / mobile carrier CGNAT). Key facts
    # about DRF throttling that drive these numbers:
    #   * AnonRateThrottle keys ONLY anonymous requests, by client IP.
    #   * UserRateThrottle keys authenticated requests by USER pk (so logged-in
    #     users are NEVER collectively throttled by IP), but falls back to IP for
    #     anonymous requests — so anonymous users behind one NAT share BOTH the
    #     `anon` and `user` IP buckets. The rates below are therefore generous
    #     enough that a roomful of people behind one IP browsing public pages does
    #     not trip a false 429.
    #   * The post-deploy E2E hits the API from CI source IPs (distinct from real
    #     users), so it consumes its OWN anon/IP buckets and cannot exhaust the
    #     bucket a real user is on; authenticated E2E traffic is keyed per test
    #     user. Either way real users are insulated.
    "DEFAULT_THROTTLE_RATES": {
        # Anonymous browsing of public pages fires many parallel reads per load.
        # Per-IP, so this is the whole-office ceiling — keep it high.
        "anon": "12000/hour",  # ~200/min per IP (was 2000/hr — NAT'd offices tripped 429)
        # Per authenticated USER (not IP). A busy dashboard polls several
        # endpoints; ~600/min headroom keeps real usage well clear of 429.
        "user": "36000/hour",  # ~600/min per user (was 6000/hr)
        "auth": "60/minute",  # register/social/OTP-resend per IP; was 20 — too tight behind NAT
        "token_refresh": "600/minute",  # refresh is per-IP + high-frequency; a 429 here logs users out, so keep it loose (gated by refresh-token validity)
        "lab_start": "60/hour",  # Limit lab provisioning (DoS protection) — per user
        "login": "10/minute",  # FAILED attempts per (IP+email); successes are never throttled
        "otp": "10/minute",  # was 5 — legitimate resends behind a shared IP
        "password_reset": "8/minute",  # allow a few retries (mistyped email) without "too many requests"
        "payment": "30/hour",  # per user
        "interview": "200/day",  # per user — long practice sessions
        "strict_anon": "240/minute",  # public browsing behind NAT needs real headroom (was 60)
        # Public, anonymous "Playgrounds" (try-instantly sandboxes). Each POST
        # runs one simulated command / SQL statement / code snippet, so this is
        # the per-IP ceiling on playground *actions*. Generous enough for a real
        # person experimenting behind a shared NAT, tight enough that the
        # ephemeral sandboxes can't be hammered into a resource problem.
        "playground": "120/minute",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "NUM_PROXIES": 1,
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

# Custom JWT authentication that also accepts cookies (see apps/auth_app/cookie_auth.py)
COOKIE_BASED_JWT_AUTH = True


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
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "JWT RSA keys not configured in production — set JWT_RSA_PRIVATE_KEY, "
            "JWT_SIGNING_KEY, or JWT_ALGORITHM=HS256 with JWT_HS256_SECRET"
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
                    "db": 3,
                    **({"password": _channels_redis_password} if _channels_redis_password else {}),
                }
            ] if _channels_redis_password else [{"address": (_channels_redis_host, _channels_redis_port), "db": 3}],
            "capacity": 1500,
            "expiry": 60,
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
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_MAX_RETRIES = 3
CELERY_TASK_RETRY_BACKOFF = True        # Exponential backoff between retries
CELERY_TASK_RETRY_BACKOFF_MAX = 600     # Cap backoff at 10 minutes
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "max_retries": 3,
    "interval_start": 0,
    "interval_step": 0.2,
    "interval_max": 0.5,
}
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
    "celery_app.tasks.cleanup_expired_otps": {"queue": "maintenance"},
    "celery_app.tasks.cleanup_expired_tokens": {"queue": "maintenance"},
    "celery_app.tasks.cleanup_old_notifications": {"queue": "maintenance"},
    "celery_app.tasks.process_subscription_expiry": {"queue": "maintenance"},
    "celery_app.tasks.send_marketing_nurture_emails": {"queue": "maintenance"},
    "celery_app.tasks.process_inactive_accounts": {"queue": "maintenance"},
    "billing.fail_stuck_payment_transactions": {"queue": "maintenance"},
    "billing.retry_invoice_creation": {"queue": "default"},
    "monitoring.check_business_signals": {"queue": "maintenance"},
    "apps.notifications.tasks.*": {"queue": "notifications"},
    "audit.create_log": {"queue": "default"},
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
# When false, skip JWT session invalidation checks (parallel E2E logins).
JWT_SESSION_ENFORCEMENT = env.bool("JWT_SESSION_ENFORCEMENT", default=True)

# --------------------------------------------------
# Configurable Contact Emails
# --------------------------------------------------
PRIMARY_EMAIL = env("PRIMARY_EMAIL", default="fixitlab@gmail.com")
PAYMENT_EMAIL = env("PAYMENT_EMAIL", default="kubelearn464@gmail.com")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", default="fixitlab.techsupport@gmail.com")
# Inbox that receives Teams/Org "Contact Sales" inquiries.
SALES_INBOX = env("SALES_INBOX", default="fixitlab.admin@gmail.com")

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
# Indian GST (tax on paid subscriptions / orders)
# --------------------------------------------------
# PRODUCTION_AUDIT FIN-01: a registered Indian seller must compute GST
# server-side and itemise it on the tax invoice. GST is charged (the price the
# user sees + pays is GST-inclusive) ONLY when:
#   * GST_ENABLED is true, AND
#   * BUSINESS_GSTIN is configured (you cannot levy GST without a registration).
# Until the owner sets a live BUSINESS_GSTIN, gst_should_charge() returns False
# and orders are priced at the bare catalog price with zero tax — so nothing
# breaks pre-registration, and the schema/breakup is already in place.
#
# GST_RATE is the combined rate for digital services (default 18% = 0.18). The
# intra-state split is CGST + SGST (each = rate/2); inter-state is a single IGST
# at the full rate. Place of supply is the seller's state unless the customer
# provides a different state (B2B with GSTIN).
GST_ENABLED = env.bool("GST_ENABLED", default=False)
GST_RATE = Decimal(str(env("GST_RATE", default="0.18")))
# Seller's state of registration (place of supply for intra-state vs inter-state).
BUSINESS_STATE = env("BUSINESS_STATE", default="")
GST_HSN_SAC = env("GST_HSN_SAC", default="998314")  # SAC for IT software/online services

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

# Per-user concurrent-lab ceiling (one user can't hold the whole engine).
MAX_CONCURRENT_LABS_PER_USER = env.int("MAX_CONCURRENT_LABS_PER_USER", default=2)
# Platform-wide concurrent-lab ceiling (PRODUCTION_AUDIT SCALE-01). There is a
# single Docker labs engine (D4); once its RAM/CPU saturate, the (N+1)th
# provision throws and surfaces a 500. This cap is checked atomically in
# StartLabView BEFORE provisioning so concurrent starts shed gracefully with a
# friendly 503 instead. Counts containerful sessions in RUNNING/PROVISIONING.
# Tune to the engine's real capacity (≈ engine RAM / per-container mem_limit).
MAX_CONCURRENT_LABS = env.int("MAX_CONCURRENT_LABS", default=60)
DOCKER_SOCKET = env("DOCKER_SOCKET", default="unix:///var/run/docker.sock")
DOCKER_NETWORK = env("DOCKER_NETWORK", default="fixitlab_labs")
DOCKER_SCENARIO_IMAGE_PREFIX = env("DOCKER_SCENARIO_IMAGE_PREFIX", default="fixitlab/scenario-")
DOCKER_CONTAINER_MEMORY_LIMIT = env("DOCKER_CONTAINER_MEMORY_LIMIT", default="512m")
DOCKER_CONTAINER_CPU_LIMIT = env.float("DOCKER_CONTAINER_CPU_LIMIT", default=1.0)

# --------------------------------------------------
# Code-execution sandbox (SECURITY_AUDIT C-01)
# --------------------------------------------------
# When True, the coding-IDE grader (apps.labs.code_exec) runs each user
# submission inside a throwaway Docker container on the labs engine
# (DOCKER_SOCKET) with --network none, a read-only rootfs, a non-root user,
# cap-drop ALL, no-new-privileges, a pids limit, and hard memory/CPU caps —
# the only backend that isolates network + host filesystem from user code.
# SECURITY_AUDIT S-01: this now defaults TRUE in production (DEBUG=False) so the
# coding-IDE grader runs untrusted user code inside the locked-down container
# (the backend container bind-mounts docker.sock for trusted monitoring only —
# user code must never reach it). In production, when the container backend is
# unavailable, the grader FAILS CLOSED (returns needs_review) rather than
# executing user code in-process on the host (see apps.labs.code_exec._execute).
# In dev/CI (DEBUG=True) it defaults False so the in-process rlimit subprocess
# keeps grading working without a Docker engine. The pass/fail decision is
# identical across backends and always fails closed.
SANDBOX_DOCKER = env.bool("SANDBOX_DOCKER", default=(not DEBUG))
# Tiny interpreter base images pulled once onto the labs Docker engine.
SANDBOX_PYTHON_IMAGE = env("SANDBOX_PYTHON_IMAGE", default="python:3.12-alpine")
SANDBOX_NODE_IMAGE = env("SANDBOX_NODE_IMAGE", default="node:20-alpine")

# Explicit path to the cluster topology file (infra/digitalocean/cluster.json).
# When unset, cluster_topology falls back to <repo>/infra/... — but inside the
# backend container BASE_DIR is /app, so the fallback resolves to /infra (not
# mounted). Setting this (with the ./infra:/app/infra mount in compose) lets the
# fleet monitor read the 4-droplet topology instead of showing a single host.
CLUSTER_TOPOLOGY_FILE = env("CLUSTER_TOPOLOGY_FILE", default="")

# --------------------------------------------------
# Fleet server monitoring (FREE — no paid APM)
# --------------------------------------------------
# Friendly name for THIS node, shown on its monitoring card. Resolution order:
#   1. MONITORING_NODE_NAME (explicit override)
#   2. CLUSTER_ROLE (edge/app/data/labs) — set per node by the cluster deploy.
#      The backend runs in a container whose hostname is a random Docker id and
#      whose IP is a bridge address, so it can NOT be matched to cluster.json by
#      hostname/IP; the role is the stable identity that lets the fleet view
#      attach this node's live host metrics to the right card.
#   3. the container/host hostname (single-host / dev fallback)
MONITORING_NODE_NAME = (
    env("MONITORING_NODE_NAME", default="")
    or env("CLUSTER_ROLE", default="")
    or socket.gethostname()
)
# Shared secret an aggregator presents to a remote node's metrics endpoint
# (header: X-Monitoring-Token). Lets the fleet endpoint pull peer metrics
# without a logged-in admin session. Optional — admins are always allowed.
MONITORING_AGENT_TOKEN = env("MONITORING_AGENT_TOKEN", default="")
# Comma-separated list of peer nodes to aggregate in the fleet view, e.g.
#   MONITORING_SERVERS="web1=https://10.0.0.11,web2=https://10.0.0.12:8000"
# Each entry is "name=base_url"; "=base_url" or bare "base_url" also work.
# The aggregator appends the metrics path to base_url and reads each peer.
MONITORING_SERVERS = [
    s.strip() for s in env("MONITORING_SERVERS", default="").split(",") if s.strip()
]
# Path appended to each peer base_url to fetch its node metrics.
MONITORING_METRICS_PATH = env(
    "MONITORING_METRICS_PATH", default="/api/admin/monitoring/metrics/"
)
# Docker socket the monitoring views use to enumerate THIS node's own system
# containers (backend / celery / etc.). In the single-host topology this is the
# same engine as DOCKER_SOCKET. In the 4-droplet cluster, DOCKER_SOCKET points at
# the remote *labs* engine (ssh://root@D4) which runs only ephemeral lab
# containers, so the system-container list must read the LOCAL daemon instead —
# the app node mounts /var/run/docker.sock for exactly this. Falls back cleanly
# when no local socket is mounted (the list just degrades to topology synthesis).
MONITORING_LOCAL_DOCKER_SOCKET = env(
    "MONITORING_LOCAL_DOCKER_SOCKET", default="unix:///var/run/docker.sock"
)

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
# SECURITY_AUDIT I-04 (revised): the admin IP allowlist is an OPTIONAL network
# layer ON TOP of authentication — every /api/admin/ endpoint already requires a
# logged-in superuser (IsAdminUser), and /django-admin/ requires staff login.
#
# Originally this defaulted TRUE in prod, which fail-CLOSED the entire admin
# surface whenever ADMIN_ALLOWED_IPS was unset — locking the owner out of all
# admin panels (you can't populate the allowlist from an admin panel you can't
# reach). It now defaults FALSE: with no allowlist, admin is reachable but still
# gated by superuser auth (standard Django posture). Set ADMIN_ALLOWED_IPS to
# your egress IP(s) AND ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=1 to additionally
# restrict admin to those networks. Loopback / in-container callers (health
# checks + server-side E2E) are always allowed.
ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST = env.bool(
    "ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST", default=False
)
# Number of trusted reverse-proxy hops in front of Django (our nginx gateway).
# Used to read the un-spoofable client IP from the RIGHT of X-Forwarded-For
# (SECURITY_AUDIT A-01). Keep in sync with the gateway: a single nginx = 1.
GATEWAY_PROXY_HOPS = env.int("GATEWAY_PROXY_HOPS", default=1)
if not DEBUG and not ADMIN_ALLOWED_IPS and not ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST:
    import warnings
    warnings.warn(
        "ADMIN_ALLOWED_IPS is not set — admin endpoints are accessible from all IPs. "
        "Set ADMIN_ALLOWED_IPS (and ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=1) in production.",
        stacklevel=2,
    )

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
# Demo payments only when explicitly enabled (local dev); never default on in production.
# SECURITY_AUDIT P-02: demo payments activate a subscription WITHOUT a real,
# signature-verified gateway charge. That must never happen in production. We
# FAIL CLOSED here: regardless of what the (operator-controlled) env says, demo
# mode is forced OFF whenever DEBUG is False, so a stale ``DEMO_PAYMENT_ENABLED=true``
# in .env.production can no longer enable free subscriptions. The payment-
# verifier helpers are independently gated on DEBUG too (defence in depth). The
# server env should still be corrected to DEMO_PAYMENT_ENABLED=false (reported).
DEMO_PAYMENT_ENABLED = env.bool("DEMO_PAYMENT_ENABLED", default=False)
if DEMO_PAYMENT_ENABLED and not DEBUG:
    import warnings
    warnings.warn(
        "DEMO_PAYMENT_ENABLED=true is ignored in production (DEBUG=False) — "
        "forcing it OFF so subscriptions require a verified gateway payment. "
        "Set DEMO_PAYMENT_ENABLED=false in .env.production to silence this.",
        stacklevel=2,
    )
    DEMO_PAYMENT_ENABLED = False

# --------------------------------------------------
# Sentry error tracking (PRODUCTION_AUDIT OBS-01)
# --------------------------------------------------
# Fully gated on SENTRY_DSN: when the DSN is empty (the default deploy) NOTHING
# is initialised and this block is a no-op. The owner sets SENTRY_DSN in
# Vault/env to turn error+performance tracking on. Init is also wrapped so a
# missing/incompatible sentry-sdk can never crash startup.
SENTRY_DSN = env("SENTRY_DSN", default="")


def _sentry_before_send(event, hint):
    """Scrub PII / secrets from every event before it leaves the process.

    send_default_pii is already False, but request bodies, headers, and cookies
    can still carry auth cookies, bearer tokens, passwords and similar. We
    redact those defensively so they never reach Sentry. Never raises — on any
    error we drop the request payload rather than risk shipping secrets.
    """
    _SENSITIVE_KEYS = {
        "password", "passwd", "pwd", "secret", "token", "access_token",
        "refresh_token", "access", "refresh", "authorization", "auth",
        "api_key", "apikey", "client_secret", "csrftoken", "csrfmiddlewaretoken",
        "sessionid", "set-cookie", "cookie", "x-csrftoken", "x-api-key",
    }
    _REDACTED = "[redacted]"

    def _scrub(obj):
        if isinstance(obj, dict):
            return {
                k: (_REDACTED if str(k).lower() in _SENSITIVE_KEYS else _scrub(v))
                for k, v in obj.items()
            }
        if isinstance(obj, (list, tuple)):
            return [_scrub(v) for v in obj]
        return obj

    try:
        request = event.get("request")
        if isinstance(request, dict):
            # Never ship cookies; redact sensitive headers / query / body fields.
            request.pop("cookies", None)
            for field in ("headers", "data", "query_string"):
                if field in request:
                    request[field] = _scrub(request[field])
        # Strip auth cookie/token-bearing extra context if present.
        if isinstance(event.get("extra"), dict):
            event["extra"] = _scrub(event["extra"])
    except Exception:  # noqa: BLE001 — scrubbing must never break event delivery
        event.pop("request", None)
    return event


if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
            send_default_pii=False,
            before_send=_sentry_before_send,
            environment=env("SENTRY_ENVIRONMENT", default=("production" if not DEBUG else "development")),
            release=env("SENTRY_RELEASE", default=None),
        )
    except Exception:  # noqa: BLE001 — never let observability wiring crash boot
        import warnings

        warnings.warn(
            "SENTRY_DSN set but sentry_sdk init failed; continuing without Sentry",
            stacklevel=1,
        )

# --------------------------------------------------
# Operational alerting (PRODUCTION_AUDIT OBS-02)
# --------------------------------------------------
# A small alerting utility (common.alerting) posts to a webhook and/or emails
# when a business-critical signal crosses a threshold. ENTIRELY GATED: when both
# ALERT_WEBHOOK_URL and ALERT_EMAIL are empty (the default deploy) common.alerting
# does NO network/email I/O — it only logs. The owner sets ALERT_WEBHOOK_URL
# (Slack/Discord/generic incoming webhook) and/or ALERT_EMAIL in Vault/env.
ALERT_WEBHOOK_URL = env("ALERT_WEBHOOK_URL", default="")
ALERT_EMAIL = env("ALERT_EMAIL", default="")
# Optional short tag prefixed to every alert (e.g. "prod", "staging").
ALERT_ENV_PREFIX = env("ALERT_ENV_PREFIX", default=("prod" if not DEBUG else ""))

# Thresholds for the business-signal monitor (celery_app.tasks_monitoring).
# Sane defaults; all overridable via env. The monitor runs on Celery Beat and
# is a no-op for alerting until a channel above is configured.
ALERT_PAYMENT_FAILURE_WINDOW_MINUTES = env.int("ALERT_PAYMENT_FAILURE_WINDOW_MINUTES", default=60)
ALERT_PAYMENT_FAILURE_THRESHOLD = env.int("ALERT_PAYMENT_FAILURE_THRESHOLD", default=10)
# Dead-man's-switch: alert if the last successful backup is older than this.
# Daily backups run at 02:30; 26h leaves headroom for a single missed run.
ALERT_BACKUP_MAX_AGE_HOURS = env.float("ALERT_BACKUP_MAX_AGE_HOURS", default=26.0)
ALERT_CELERY_QUEUE_THRESHOLD = env.int("ALERT_CELERY_QUEUE_THRESHOLD", default=200)
ALERT_LOGIN_FAILURE_WINDOW_MINUTES = env.int("ALERT_LOGIN_FAILURE_WINDOW_MINUTES", default=15)
ALERT_LOGIN_FAILURE_THRESHOLD = env.int("ALERT_LOGIN_FAILURE_THRESHOLD", default=50)
# How often the monitor runs (minutes). Kept as a setting so the beat schedule
# and any docs stay in sync.
ALERT_MONITOR_INTERVAL_MINUTES = env.int("ALERT_MONITOR_INTERVAL_MINUTES", default=5)

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
            # Resilience: if Redis is unreachable/slow/pool-exhausted, treat the
            # cache as a miss instead of raising. Cached endpoints (technologies,
            # scenarios, stats, /config/, leaderboard, progress) all do
            # cache.get(...) at the top — without this, a Redis hiccup turns
            # EVERY one of them into a 500, blanking public pages and firing the
            # global "Server error" toast site-wide. With IGNORE_EXCEPTIONS they
            # fall through to the DB and serve fresh data instead.
            "IGNORE_EXCEPTIONS": True,
        },
    }
}

# Log the swallowed Redis errors (at WARNING) so degraded cache is observable.
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True

# --------------------------------------------------
# Security (all environments)
# --------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# SECURITY_AUDIT A-01: require a custom JS header (X-Requested-With) on
# cookie-authenticated state-changing requests so a cross-site form POST can't
# ride the httpOnly access_token cookie. The Bearer-header path (the SPA's
# default for authenticated calls) is unaffected. See apps.auth_app.cookie_auth.
COOKIE_AUTH_REQUIRE_CSRF_HEADER = env.bool(
    "COOKIE_AUTH_REQUIRE_CSRF_HEADER", default=True
)
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

# Always enforce secure cookies regardless of DEBUG mode
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# --------------------------------------------------
# Security (production only)
# --------------------------------------------------
if not DEBUG:
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

