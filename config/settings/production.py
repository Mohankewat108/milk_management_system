from . import base as _base

for _setting_name, _setting_value in vars(_base).items():
    if _setting_name.isupper():
        globals()[_setting_name] = _setting_value

env = _base.env
SECRET_KEY = _base.SECRET_KEY
ALLOWED_HOSTS = _base.ALLOWED_HOSTS
DJANGO_SITE_URL = _base.DJANGO_SITE_URL
DATABASES = _base.DATABASES
EMAIL_BACKEND = _base.EMAIL_BACKEND
REDIS_URL = _base.REDIS_URL

DEBUG = False

if SECRET_KEY.startswith("unsafe-development-key"):
    raise RuntimeError("Set DJANGO_SECRET_KEY to a strong secret in production.")
if not ALLOWED_HOSTS:
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS in production.")
if not DJANGO_SITE_URL:
    raise RuntimeError("Set DJANGO_SITE_URL to the canonical public HTTPS origin in production.")
if not DJANGO_SITE_URL.startswith("https://"):
    raise RuntimeError("Production DJANGO_SITE_URL must use HTTPS.")
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise RuntimeError("Production must use PostgreSQL; SQLite is not supported.")
if EMAIL_BACKEND.endswith("console.EmailBackend"):
    raise RuntimeError("Configure a real transactional email backend in production.")
if not env("EMAIL_HOST", default=""):
    raise RuntimeError("Set EMAIL_HOST for production email delivery.")
if not env("EMAIL_HOST_USER", default=""):
    raise RuntimeError("Set EMAIL_HOST_USER for production email delivery.")
if not env("EMAIL_HOST_PASSWORD", default=""):
    raise RuntimeError("Set EMAIL_HOST_PASSWORD for production email delivery.")
if not env("DEFAULT_FROM_EMAIL", default=""):
    raise RuntimeError("Set DEFAULT_FROM_EMAIL for production email delivery.")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REDIRECT_EXEMPT = []

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "dairynexus",
        "TIMEOUT": 300,
    }
}
if not REDIS_URL.startswith(("redis://", "rediss://")):
    raise RuntimeError("Production REDIS_URL must use redis:// or rediss://.")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)

DEFAULT_FILE_STORAGE = env(
    "DJANGO_DEFAULT_FILE_STORAGE",
    default="django.core.files.storage.FileSystemStorage",
)
SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ["'self'"],
    "base-uri": ["'self'"],
    "frame-ancestors": ["'none'"],
    "form-action": ["'self'"],
    "object-src": ["'none'"],
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
