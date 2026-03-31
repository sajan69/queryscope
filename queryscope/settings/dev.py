"""Development settings."""

from decouple import config

from .base import *  # noqa: F403

DEBUG = config("DEBUG", default=True, cast=bool)  # noqa: F405

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# LocMem cache by default; swap to Redis when REDIS is available (later milestone)
if config("USE_REDIS_CACHE", default=False, cast=bool):
    CACHES = {  # noqa: F405
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,  # noqa: F405
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
