from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import SECRET_KEY, env_list

DEBUG = False

# Refuse to run with a placeholder or short secret: a guessable key would let anyone forge tokens.
if len(SECRET_KEY) < 32 or SECRET_KEY.lower().startswith(("change-me", "changeme", "ci-only", "build-only")):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a random value of at least 32 characters in production.")

SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]  # container health checks speak plain HTTP inside the network
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
