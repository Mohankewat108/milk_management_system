from .base import *  # noqa: F403

DEBUG = False
if SECRET_KEY.startswith("unsafe-development-key"):
    raise RuntimeError("Set DJANGO_SECRET_KEY to a strong secret in production.")
if not ALLOWED_HOSTS:
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS in production.")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
