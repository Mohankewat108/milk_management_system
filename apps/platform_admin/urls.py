from django.urls import path

from .views import dashboard, organization_create

app_name = "platform"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("farms/create/", organization_create, name="organization_create"),
]
