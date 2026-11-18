from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse


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
    """Readiness endpoint: reject traffic when schema migrations are missing or pending."""
    try:
        executor = MigrationExecutor(connection)
        if executor.loader.unmigrated_apps:
            return JsonResponse(
                {"status": "unready", "reason": "apps_without_migrations"},
                status=503,
            )
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception:
        return JsonResponse(
            {"status": "unready", "reason": "migration_state_unavailable"},
            status=503,
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
