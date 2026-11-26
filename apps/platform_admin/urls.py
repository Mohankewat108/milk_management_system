from django.urls import path

from .views import (
    dashboard,
    organization_create,
    organization_delete,
    organization_resend_invitation,
    organization_reset_owner_password,
    organization_set_status,
    owner_invitation_accept,
)

app_name = "platform"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("farms/create/", organization_create, name="organization_create"),
    path(
        "farms/<uuid:organization_id>/reset-owner-password/",
        organization_reset_owner_password,
        name="organization_reset_owner_password",
    ),
    path(
        "farms/<uuid:organization_id>/delete/",
        organization_delete,
        name="organization_delete",
    ),
    path(
        "farms/<uuid:organization_id>/status/",
        organization_set_status,
        name="organization_set_status",
    ),
    path(
        "farms/<uuid:organization_id>/resend-invitation/",
        organization_resend_invitation,
        name="organization_resend_invitation",
    ),
    path(
        "invitations/<uuid:invitation_id>/<str:token>/",
        owner_invitation_accept,
        name="owner_invitation_accept",
    ),
]
