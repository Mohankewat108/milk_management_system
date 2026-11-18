from django.urls import path

from . import views
from .staff_views import staff_list, staff_membership_status, staff_invitation_revoke

app_name = "business"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("register/", views.register_business, name="register"),
    path("<slug:organization_slug>/", views.dashboard, name="dashboard"),
    path("<slug:organization_slug>/branches/", views.branches, name="branches"),
    path("<slug:organization_slug>/staff/", staff_list, name="staff"),
    path("<slug:organization_slug>/staff/<uuid:membership_id>/status/", staff_membership_status, name="staff_status"),
    path("<slug:organization_slug>/staff/invitations/<uuid:invitation_id>/revoke/", staff_invitation_revoke, name="staff_invitation_revoke"),
]
