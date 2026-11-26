from django.contrib import admin
from django.urls import include, path

from apps.core.views import health_check, landing_page, nepali_calendar_month, readiness_check
from apps.core.mobile import app_home, mobile_manifest, mobile_offline, mobile_service_worker

urlpatterns = [
    path("app/", app_home, name="mobile_app"),
    path("app/manifest.json", mobile_manifest, name="mobile_manifest"),
    path("app/service-worker/", mobile_service_worker, name="mobile_service_worker"),
    path("app/offline/", mobile_offline, name="mobile_offline"),
    path("healthz/", health_check, name="healthz"),
    path("readyz/", readiness_check, name="readyz"),
    path("api/calendar/nepali/", nepali_calendar_month, name="nepali_calendar_month"),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("accounts/", include("apps.accounts.urls")),
    path("business/", include("apps.organizations.urls")),
    path("business/", include("apps.parties.urls")),
    path("business/", include("apps.collections.urls")),
    path("business/", include("apps.pricing.urls")),
    path("business/", include("apps.finance.urls")),
    path("business/", include("apps.inventory.urls")),
    path("business/", include("apps.data_exports.urls")),
    path("platform/", include("apps.platform_admin.urls")),
    path("portal/", include("apps.parties.customer_urls")),
    path("farmer/", include("apps.parties.farmer_urls")),
    path("", landing_page, name="home"),
]
