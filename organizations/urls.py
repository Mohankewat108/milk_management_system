from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('platform/', views.platform_dashboard, name='platform_dashboard'),
    path('platform/organisations/', views.platform_organisations, name='platform_organisations'),
    path('platform/organisations/<uuid:organisation_id>/status/', views.platform_org_status, name='platform_org_status'),
]
