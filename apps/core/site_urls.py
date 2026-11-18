"""Helpers for generating links on the configured public site."""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def build_site_absolute_uri(request, path):
    """Build an absolute URL using the canonical site URL when configured.

    The request host is retained as a development fallback so Django's test
    client and local development continue to work without extra configuration.
    """
    if not path.startswith("/"):
        raise ValueError("Site-relative paths must start with '/'.")

    site_url = getattr(settings, "DJANGO_SITE_URL", "").strip()
    if not site_url:
        return request.build_absolute_uri(path)

    parsed = urlsplit(site_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ImproperlyConfigured(
            "DJANGO_SITE_URL must be an absolute http(s) origin, "
            "for example https://your-domain.example"
        )

    return f"{site_url.rstrip('/')}{path}"
