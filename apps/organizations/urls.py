from django.urls import path

from . import views

app_name = "business"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("register/", views.register_business, name="register"),
    path("<slug:organization_slug>/", views.dashboard, name="dashboard"),
    path("<slug:organization_slug>/branches/", views.branches, name="branches"),
]
