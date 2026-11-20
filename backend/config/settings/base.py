"""Base settings shared by all environments. Secrets come from the environment only."""

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def env_list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "rest_framework_simplejwt.token_blacklist",
    "shared",
    "apps.accounts",
    "apps.audit",
    "apps.datasets",
    "apps.transactions",
    "apps.model_registry",
    "apps.detection",
    "apps.behavior",
    "apps.graph_engine",
    "apps.duplicates",
    "apps.risk_engine",
    "apps.explain",
    "apps.alerts",
    "apps.cases",
    "apps.analytics",
]

MIDDLEWARE = [
    "shared.middleware.RequestIDMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}
AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.BCryptSHA256PasswordHasher"]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Imports (Phase 4) ---
# Model artifacts (joblib) are only loaded from this directory, and only when their SHA-256 matches the registry.
ML_ARTIFACTS_DIR = Path(env("FINGUARD_DATASETS_DIR", "/datasets")) / "artifacts"
# NEO4J_TARGET=local (default, the compose container) or aura (a Neo4j Aura instance, NEO4J_AURA_* in .env).
if env("NEO4J_TARGET", "local") == "aura":
    NEO4J_URI = env("NEO4J_AURA_URI", "")
    NEO4J_USER = env("NEO4J_AURA_USERNAME", "neo4j")
    NEO4J_PASSWORD = env("NEO4J_AURA_PASSWORD", "")
    NEO4J_DATABASE = env("NEO4J_AURA_DATABASE", "") or None
else:
    NEO4J_URI = env("NEO4J_URI", "bolt://neo4j:7687")
    NEO4J_USER = env("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = env("NEO4J_PASSWORD", "")
    NEO4J_DATABASE = None
# Email (alert notifications). Development prints to the console; set EMAIL_BACKEND and EMAIL_* for SMTP.
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "25"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", "0") == "1"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "FinGuard <noreply@finguard.local>")
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", "http://localhost:5173")
PASSWORD_RESET_TIMEOUT = 3600  # seconds a reset link stays valid
CASE_EVIDENCE_MAX_BYTES = int(env("CASE_EVIDENCE_MAX_BYTES", str(20 * 1024**2)))
# Four-eyes closure: when on, the person who closes a case must differ from the person who resolved it (docs/10, D-014).
CASE_CLOSE_REQUIRES_DIFFERENT_USER = env("CASE_CLOSE_REQUIRES_DIFFERENT_USER", "0") == "1"
RISK_MAX_ROWS = int(env("RISK_MAX_ROWS", "2000000"))
INVOICE_MAX_BYTES = int(env("INVOICE_MAX_BYTES", str(10 * 1024**2)))
DUPLICATE_MAX_ROWS = int(env("DUPLICATE_MAX_ROWS", "2000000"))
GRAPH_MAX_ROWS = int(env("GRAPH_MAX_ROWS", "2000000"))
BEHAVIOR_MAX_ROWS = int(env("BEHAVIOR_MAX_ROWS", "2000000"))
DETECTION_MAX_ROWS = int(env("DETECTION_MAX_ROWS", "2000000"))
IMPORT_MAX_CSV_BYTES = int(env("IMPORT_MAX_CSV_BYTES", str(2 * 1024**3)))
IMPORT_MAX_XLSX_BYTES = int(env("IMPORT_MAX_XLSX_BYTES", str(100 * 1024**2)))
IMPORT_MAX_XLSX_UNCOMPRESSED = 1024**3  # zip-bomb guard
IMPORT_CHUNK_ROWS = int(env("IMPORT_CHUNK_ROWS", "50000"))
IMPORT_MAX_STORED_ERRORS = 10_000  # per job; further rejects are counted but not stored
IMPORT_PREVIEW_ROWS = 20
IMPORT_API_MAX_BATCH = 1000
IMPORT_STORAGE_SUBDIR = "imports"

REDIS_URL = env("REDIS_URL", "redis://redis:6379/0")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "shared.exceptions.api_exception_handler",
    # Default deny: authenticated AND the view must declare a permission (apps.accounts.permissions).
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "apps.accounts.permissions.HasRolePermission",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min", "user": "600/min", "login": "10/min", "refresh": "30/min",
        "register": "5/hour", "password_reset": "5/hour", "verify": "30/hour",
    },
}
SPECTACULAR_SETTINGS = {
    "TITLE": "FinGuard API",
    "DESCRIPTION": "Financial anomaly detection and investigation platform.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=8),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Cache (throttling counters) uses Redis DB 1 so clearing it never touches the Celery broker on DB 0.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL.rsplit("/", 1)[0] + "/1",
    }
}

CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 60
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "analytics-refresh-hourly": {"task": "analytics.refresh_all", "schedule": 3600.0},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": ('{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}')
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
