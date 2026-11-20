from django.urls import path

from .views import farmer_portal

app_name = "farmer_portal"

urlpatterns = [path("", farmer_portal, name="home")]
