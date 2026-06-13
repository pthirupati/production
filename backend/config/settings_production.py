"""
Production-only Django settings.
Strict security, no debug, no development tools exposed.
"""

from pathlib import Path
import environ
import os
from datetime import timedelta

# ──────────────────────────────────────────────────────────────
# PRODUCTION SETTINGS ONLY
# ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR.parent, ".env"))

# ── SECURITY: NO DEBUG IN PRODUCTION ──
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = False  # MUST be False in production
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

if not ALLOWED_HOSTS:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set in .env for production")

# ──────────────────────────────────────────────────────────────
# DATABASE (Production PostgreSQL) ──
# ──────────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env("POSTGRES_DB"),
        'USER': env("POSTGRES_USER"),
        'PASSWORD': env("POSTGRES_PASSWORD"),
        'HOST': env("POSTGRES_HOST"),
        'PORT': env("POSTGRES_PORT", default="5432"),
        'CONN_MAX_AGE': 600,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'sslmode': 'require',  # Require SSL for production
        }
    }
}

# ──────────────────────────────────────────────────────────────
# SECURITY HEADERS (Strict for Production) ──
# ──────────────────────────────────────────────────────────────

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 28800  # 8 hours

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ("'self'",),
    "script-src": ("'self'", "https://checkout.razorpay.com", "https://cdnjs.cloudflare.com"),
    "style-src": ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com"),
    "img-src": ("'self'", "data:", "blob:", "https:"),
    "connect-src": ("'self'", "wss://fixitlab.in", "https://api.razorpay.com"),
    "font-src": ("'self'", "data:", "https://fonts.googleapis.com"),
    "frame-src": ("https://api.razorpay.com",),
    "frame-ancestors": ("'none'",),
}

SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ──────────────────────────────────────────────────────────────
# CORS - Production Domain Only ──
# ──────────────────────────────────────────────────────────────

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

if not CORS_ALLOWED_ORIGINS:
    raise ValueError("CORS_ALLOWED_ORIGINS must be set in .env for production")

# ──────────────────────────────────────────────────────────────
# JWT Security (RS256) ──
# ──────────────────────────────────────────────────────────────

SIMPLE_JWT = {
    "ALGORITHM": env("JWT_ALGORITHM", default="RS256"),
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=None),
    "VERIFYING_KEY": env("JWT_VERIFYING_KEY", default=None),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "JTI_CLAIM": "jti",
    "JTI_GENERATION_ENABLED": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

if not SIMPLE_JWT["SIGNING_KEY"]:
    SIMPLE_JWT["ALGORITHM"] = "HS256"
    SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY

# ──────────────────────────────────────────────────────────────
# LOGGING (Production JSON) ──
# ──────────────────────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "common.logging_utils.JSONFormatter",
        },
    },
    "handlers": {
        "console_json": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "level": "INFO",
        },
    },
    "root": {
        "handlers": ["console_json"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console_json"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console_json"],
            "level": "INFO",
            "propagate": False,
        },
        "common.security": {
            "handlers": ["console_json"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ──────────────────────────────────────────────────────────────
# REDIS Cache (Session Tracking) ──
# ──────────────────────────────────────────────────────────────

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{env('REDIS_HOST', default='redis')}:{env('REDIS_PORT', default='6379')}/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PASSWORD": env("REDIS_PASSWORD", default=None),
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        }
    }
}

# ──────────────────────────────────────────────────────────────
# REST Framework - Production Settings ──
# ──────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",  # JSON only (no HTML browsable API in prod)
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "lab_start": "60/hour",
        "auth": "30/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

# ──────────────────────────────────────────────────────────────
# PAYMENT GATEWAYS ──
# ──────────────────────────────────────────────────────────────

RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default=None)
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default=None)
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default=None)
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default=None)
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default=None)

# ──────────────────────────────────────────────────────────────
# INSTALLED APPS (Production Only) ──
# ──────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    # Django core
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # API
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    
    # Async & Real-time
    "channels",
    
    # Background Jobs
    "django_celery_results",
    "django_celery_beat",
    
    # Filtering
    "django_filters",
    
    # Local apps
    "apps.accounts",
    "apps.question_bank",
    "apps.scenario_versions",
    "apps.hints",
    "apps.labs",
    "apps.terminal",
    "apps.progress",
    "apps.ratings",
    "apps.billing",
    "apps.community",
    "apps.leaderboard",
    "apps.notifications",
    "apps.audit",
    "apps.public_api",
]

# ──────────────────────────────────────────────────────────────
# MIDDLEWARE (Production Security) ──
# ──────────────────────────────────────────────────────────────

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
    
    # Security: request metadata extraction and JWT validation
    "common.middleware_security.RequestMetadataMiddleware",
    "common.middleware_security.JWTSessionValidationMiddleware",
    "common.middleware_security.SecurityHeadersMiddleware",
    
    # Audit (LAST)
    "apps.audit.middleware.AuditMiddleware",
]

# ──────────────────────────────────────────────────────────────
# STATIC FILES (WhiteNoise, Production Build)
# ──────────────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR.parent, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ──────────────────────────────────────────────────────────────
# EMAIL (SMTP for alerts) ──
# ──────────────────────────────────────────────────────────────

EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", default="587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@fixitlab.in")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", default="support@fixitlab.in")

# ──────────────────────────────────────────────────────────────
# NO URL ADMIN EXPOSURE IN PRODUCTION ──
# ──────────────────────────────────────────────────────────────

# Admin is disabled in production.
# Access only via secure tunnels or internal networks.
ADMIN_URL = env("ADMIN_URL", default="django-admin/")

# ──────────────────────────────────────────────────────────────
# CELERY (Background Tasks) ──
# ──────────────────────────────────────────────────────────────

CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# ──────────────────────────────────────────────────────────────
# CHANNELS (WebSocket) ──
# ──────────────────────────────────────────────────────────────

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(env("REDIS_HOST", default="redis"), int(env("REDIS_PORT", default="6379")))],
        },
    }
}

# ──────────────────────────────────────────────────────────────
# PRODUCTION-ONLY ENFORCEMENT ──
# ──────────────────────────────────────────────────────────────

# Ensure all production requirements are met
if DEBUG:
    raise ValueError("DEBUG=True detected in production! SECURITY RISK!")

if not SECRET_KEY or len(SECRET_KEY) < 50:
    raise ValueError("SECRET_KEY must be set and at least 50 characters long!")

if not env("DJANGO_SECRET_KEY"):
    raise ValueError("DJANGO_SECRET_KEY environment variable not set!")

# Never allow demo/bypass payments in production
DEMO_PAYMENT_ENABLED = False

if not env("RAZORPAY_KEY_ID", default="") and not env("STRIPE_SECRET_KEY", default=""):
    import warnings
    warnings.warn("No payment gateway configured in production!", stacklevel=1)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
SERVE_MEDIA = True

print("✅ Production settings loaded - Security checks passed")
