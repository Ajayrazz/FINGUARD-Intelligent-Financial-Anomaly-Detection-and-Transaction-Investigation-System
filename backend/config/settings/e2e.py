"""Settings for the isolated end-to-end test stack (compose profile `e2e`).

It uses its own database (finguard_e2e), Redis databases and media folder, and relaxed throttles so a browser test
suite can sign in many times. Never use these settings anywhere that holds real data.
"""

from pathlib import Path

from .development import *  # noqa: F401,F403
from .development import BASE_DIR, REDIS_URL, REST_FRAMEWORK  # noqa: F401

ALLOWED_HOSTS = ["backend-e2e", "localhost", "127.0.0.1"]
MEDIA_ROOT = str(Path(BASE_DIR) / "media_e2e")
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL.rsplit("/", 1)[0] + "/6"}}
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"anon": "100000/min", "user": "100000/min", "login": "1000/min", "refresh": "100000/min"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
