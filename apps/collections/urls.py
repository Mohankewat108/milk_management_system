from django.urls import path

from . import views

app_name = "collections"

urlpatterns = [
    path("<slug:organization_slug>/collections/", views.collection_list, name="list"),
    path("<slug:organization_slug>/collections/new/", views.collection_create, name="create"),
    path(
        "<slug:organization_slug>/collections/<uuid:collection_id>/edit/",
        views.collection_edit,
        name="edit",
    ),
    path(
        "<slug:organization_slug>/collections/<uuid:collection_id>/approve/",
        views.approve_collection,
        name="approve",
    ),
    path(
        "<slug:organization_slug>/collections/<uuid:collection_id>/reverse/",
        views.collection_reverse,
        name="reverse",
    ),
]
