from django.urls import path

from .views import customer_portal

app_name = "customer_portal"

urlpatterns = [path("", customer_portal, name="home")]
