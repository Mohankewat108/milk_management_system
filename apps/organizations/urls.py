from django.urls import path

from . import views
from .staff_views import staff_list

app_name = "business"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("register/", views.register_business, name="register"),
    path("<slug:organization_slug>/", views.dashboard, name="dashboard"),
    path("<slug:organization_slug>/branches/", views.branches, name="branches"),
    path("<slug:organization_slug>/staff/", staff_list, name="staff"),
]
