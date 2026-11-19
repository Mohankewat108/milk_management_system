from django.urls import path

from apps.core import management_views

from . import views
from .staff_views import staff_invitation_revoke, staff_list, staff_membership_status

app_name = "business"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("register/", views.register_business, name="register"),
    path("<slug:organization_slug>/trash/", management_views.trash_list, name="trash"),
    path(
        "<slug:organization_slug>/trash/<str:model_key>/<uuid:object_id>/delete/",
        management_views.trash_delete,
        name="trash_delete",
    ),
    path(
        "<slug:organization_slug>/trash/<str:model_key>/<uuid:object_id>/restore/",
        management_views.trash_restore,
        name="trash_restore",
    ),
    path("<slug:organization_slug>/", views.dashboard, name="dashboard"),
    path("<slug:organization_slug>/settings/", views.organization_edit, name="settings"),
    path("<slug:organization_slug>/branches/", views.branches, name="branches"),
    path(
        "<slug:organization_slug>/branches/<uuid:branch_id>/edit/",
        views.branch_edit,
        name="branch_edit",
    ),
    path("<slug:organization_slug>/staff/", staff_list, name="staff"),
    path(
        "<slug:organization_slug>/staff/<uuid:membership_id>/status/",
        staff_membership_status,
        name="staff_status",
    ),
    path(
        "<slug:organization_slug>/staff/invitations/<uuid:invitation_id>/revoke/",
        staff_invitation_revoke,
        name="staff_invitation_revoke",
    ),
]
