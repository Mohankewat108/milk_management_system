from django.contrib import admin
from django.urls import include, path

from apps.core.views import health_check, landing_page

urlpatterns = [
    path("healthz/", health_check, name="healthz"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("business/", include("apps.organizations.urls")),
    path("platform/", include("apps.platform_admin.urls")),
    path("portal/", include("apps.parties.customer_urls")),
    path("", landing_page, name="home"),
]
