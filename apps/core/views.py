from datetime import date

import nepali_datetime
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET


def health_check(request):
    """Liveness endpoint: confirm the process can reach its database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unhealthy", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


def readiness_check(request):
    """Readiness endpoint: reject traffic when database migrations are pending."""
    try:
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception:
        return JsonResponse(
            {"status": "unready", "reason": "migration_state_unavailable"}, status=503
        )
    if pending:
        return JsonResponse(
            {"status": "unready", "pending_migrations": len(pending)},
            status=503,
        )
    return JsonResponse({"status": "ready"})


def landing_page(request):
    if request.user.is_authenticated:
        return redirect(reverse("business:workspace"))
    return render(request, "public/home.html")


@require_GET
def nepali_calendar_month(request):
    """Return authoritative BS month metadata for the accessible date picker."""
    try:
        today_bs = nepali_datetime.date.from_datetime_date(date.today())
        year = int(request.GET.get("year", today_bs.year))
        month = int(request.GET.get("month", today_bs.month))
        if not 1 <= month <= 12:
            raise ValueError("month_out_of_range")
        first_day = nepali_datetime.date(year, month, 1)
        first_gregorian = first_day.to_datetime_date()
        days_in_month = 0
        for day in range(1, 33):
            try:
                nepali_datetime.date(year, month, day)
                days_in_month = day
            except ValueError:
                break
    except (TypeError, ValueError, OverflowError):
        return JsonResponse({"error": "invalid_month"}, status=400)

    month_names = [
        "बैशाख",
        "जेठ",
        "असार",
        "साउन",
        "भदौ",
        "असोज",
        "कार्तिक",
        "मंसिर",
        "पुष",
        "माघ",
        "फागुन",
        "चैत",
    ]
    return JsonResponse(
        {
            "year": year,
            "month": month,
            "month_name": month_names[month - 1],
            "days_in_month": days_in_month,
            "first_weekday": first_gregorian.weekday(),
            "today": {"year": today_bs.year, "month": today_bs.month, "day": today_bs.day},
            "days": [
                {
                    "day": day,
                    "gregorian": nepali_datetime.date(year, month, day)
                    .to_datetime_date()
                    .isoformat(),
                }
                for day in range(1, days_in_month + 1)
            ],
        }
    )
