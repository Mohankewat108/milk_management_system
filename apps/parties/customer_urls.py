from django.urls import path

from .views import customer_portal

app_name = "customer_portal"

urlpatterns = [
    path("statement.csv", customer_portal, {"format": "csv"}, name="statement_csv"),
    path("", customer_portal, name="home"),
]
