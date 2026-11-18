from django.contrib import admin
from django.urls import include, path

from apps.core.views import health_check, landing_page, readiness_check

urlpatterns = [
    path("healthz/", health_check, name="healthz"),
    path("readyz/", readiness_check, name="readyz"),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("accounts/", include("apps.accounts.urls")),
    path("business/", include("apps.organizations.urls")),
    path("business/", include("apps.parties.urls")),
    path("business/", include("apps.collections.urls")),
    path("business/", include("apps.pricing.urls")),
    path("business/", include("apps.finance.urls")),
    path("business/", include("apps.inventory.urls")),
    path("platform/", include("apps.platform_admin.urls")),
    path("portal/", include("apps.parties.customer_urls")),
    path("", landing_page, name="home"),
]
