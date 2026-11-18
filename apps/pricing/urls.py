from django.urls import path

from . import views

app_name = "pricing"

urlpatterns = [
    path("<slug:organization_slug>/pricing/", views.settings_view, name="settings"),
    path("<slug:organization_slug>/pricing/<uuid:pricing_id>/edit/", views.pricing_edit, name="edit"),
    path("<slug:organization_slug>/pricing/<uuid:pricing_id>/approve/", views.approve_pricing, name="approve"),
    path("<slug:organization_slug>/quality/", views.quality_settings, name="quality"),
]
