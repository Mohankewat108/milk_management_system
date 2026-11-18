from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unhealthy", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


def landing_page(request):
    if request.user.is_authenticated:
        return redirect(reverse("business:workspace"))
    return render(request, "public/home.html")
