from . import base as _base

for _setting_name, _setting_value in vars(_base).items():
    if _setting_name.isupper():
        globals()[_setting_name] = _setting_value

env = _base.env

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Use PostgreSQL in CI when DATABASE_URL is supplied; keep an isolated in-memory
# SQLite database for a quick local test run when it is not.
if not env("DATABASE_URL", default=""):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
