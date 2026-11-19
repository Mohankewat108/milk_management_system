from . import base as _base

for _setting_name, _setting_value in vars(_base).items():
    if _setting_name.isupper():
        globals()[_setting_name] = _setting_value

env = _base.env
ALLOWED_HOSTS = _base.ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS = _base.CSRF_TRUSTED_ORIGINS
REDIS_URL = _base.REDIS_URL

DEBUG = True

# GitHub Codespaces serves forwarded ports from *.app.github.dev.
# Keep these development-only allowances out of production settings.
ALLOWED_HOSTS = list(
    dict.fromkeys(
        [
            *ALLOWED_HOSTS,
            "localhost",
            "127.0.0.1",
            ".app.github.dev",
        ]
    )
)

CSRF_TRUSTED_ORIGINS = list(
    dict.fromkeys(
        [
            *CSRF_TRUSTED_ORIGINS,
            "http://localhost:8000",
            "https://localhost:8000",
            "http://localhost:8001",
            "https://localhost:8001",
            "https://*.app.github.dev",
        ]
    )
)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

if env.bool("DJANGO_USE_REDIS_CACHE", default=False):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "dairynexus-dev",
        }
    }
