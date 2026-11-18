"""Locale-aware date formatting for application templates."""
from datetime import date, datetime

from django import template
from django.utils import timezone, translation

from apps.core.nepali_dates import format_local_date

register = template.Library()


@register.filter
def local_date(value, date_format="Y-m-d"):
    """Render a date as Bikram Sambat in Nepali, Gregorian otherwise."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            try:
                value = date.fromisoformat(value)
            except ValueError:
                return value
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        day = value.date()
        time_part = value.strftime(" %H:%M")
    elif isinstance(value, date):
        day = value
        time_part = ""
    else:
        return value
    language_code = translation.get_language() or "en"
    return format_local_date(day, language_code) + time_part
