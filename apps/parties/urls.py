from django.urls import path

from . import business_views, management_views

app_name = "parties"

urlpatterns = [
    path(
        "<slug:organization_slug>/<str:kind>/<uuid:party_id>/collections/export/",
        business_views.party_collection_export,
        name="party_collection_export",
    ),
    path("<slug:organization_slug>/customers/", business_views.customer_list, name="customers"),
    path(
        "<slug:organization_slug>/customers/new/",
        business_views.customer_create,
        name="customer_create",
    ),
    path(
        "<slug:organization_slug>/customers/<uuid:customer_id>/",
        business_views.customer_detail,
        name="customer_detail",
    ),
    path(
        "<slug:organization_slug>/customers/<uuid:party_id>/edit/",
        management_views.party_edit,
        {"kind": "customer"},
        name="customer_edit",
    ),
    path(
        "<slug:organization_slug>/customers/<uuid:party_id>/trash/",
        management_views.party_trash,
        {"kind": "customer"},
        name="customer_trash",
    ),
    path("<slug:organization_slug>/farmers/", business_views.farmer_list, name="farmers"),
    path(
        "<slug:organization_slug>/farmers/new/", business_views.farmer_create, name="farmer_create"
    ),
    path(
        "<slug:organization_slug>/farmers/<uuid:farmer_id>/",
        business_views.farmer_detail,
        name="farmer_detail",
    ),
    path(
        "<slug:organization_slug>/farmers/<uuid:party_id>/edit/",
        management_views.party_edit,
        {"kind": "farmer"},
        name="farmer_edit",
    ),
    path(
        "<slug:organization_slug>/farmers/<uuid:party_id>/trash/",
        management_views.party_trash,
        {"kind": "farmer"},
        name="farmer_trash",
    ),
    path("<slug:organization_slug>/trash/", management_views.party_trash_list, name="trash"),
    path(
        "<slug:organization_slug>/trash/<str:kind>/<uuid:party_id>/restore/",
        management_views.party_restore,
        name="party_restore",
    ),
]
