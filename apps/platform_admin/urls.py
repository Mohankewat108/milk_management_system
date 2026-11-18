from django.urls import path

from .views import dashboard

app_name = "platform"

urlpatterns = [path("", dashboard, name="dashboard")]
