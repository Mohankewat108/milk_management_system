from django.urls import path

from .views import (
    dashboard,
    organization_create,
    organization_set_status,
    owner_invitation_accept,
)

app_name = "platform"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("farms/create/", organization_create, name="organization_create"),
    path("farms/<uuid:organization_id>/status/", organization_set_status, name="organization_set_status"),
    path(
        "invitations/<uuid:invitation_id>/<str:token>/",
        owner_invitation_accept,
        name="owner_invitation_accept",
    ),
]
