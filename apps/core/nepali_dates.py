"""Bikram Sambat date parsing and formatting helpers."""

from datetime import date

import nepali_datetime


def parse_local_date(value: str, language_code: str) -> date | None:
    """Parse YYYY-MM-DD from the active calendar into a Gregorian date."""
    value = (value or "").strip()
    if not value:
        return None
    if language_code == "ne":
        try:
            year, month, day = (int(part) for part in value.split("-"))
            return nepali_datetime.date(year, month, day).to_datetime_date()
        except (TypeError, ValueError):
            raise ValueError("Enter a valid Bikram Sambat date in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Enter a valid date in YYYY-MM-DD format.") from exc


def format_local_date(value: date, language_code: str) -> str:
    """Format a Gregorian date using BS for Nepali and AD otherwise."""
    if language_code == "ne":
        bs_date = nepali_datetime.date.from_datetime_date(value)
        return f"{bs_date.year:04d}-{bs_date.month:02d}-{bs_date.day:02d}"
    return value.strftime("%Y-%m-%d")
