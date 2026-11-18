from django.urls import path

from . import business_views

app_name = "parties"

urlpatterns = [
    path("<slug:organization_slug>/customers/", business_views.customer_list, name="customers"),
    path("<slug:organization_slug>/customers/new/", business_views.customer_create, name="customer_create"),
    path("<slug:organization_slug>/customers/<uuid:customer_id>/", business_views.customer_detail, name="customer_detail"),
    path("<slug:organization_slug>/farmers/", business_views.farmer_list, name="farmers"),
    path("<slug:organization_slug>/farmers/new/", business_views.farmer_create, name="farmer_create"),
    path("<slug:organization_slug>/farmers/<uuid:farmer_id>/", business_views.farmer_detail, name="farmer_detail"),
]
