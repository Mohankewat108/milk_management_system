from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("<slug:organization_slug>/inventory/", views.item_list, name="items"),
    path("<slug:organization_slug>/inventory/new/", views.item_create, name="item_create"),
    path("<slug:organization_slug>/inventory/movements/new/", views.movement_create, name="movement_create"),
    path("<slug:organization_slug>/suppliers/", views.supplier_list, name="suppliers"),
]
