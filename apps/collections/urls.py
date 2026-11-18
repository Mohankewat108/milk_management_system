from django.urls import path

from . import views

app_name = "collections"

urlpatterns = [
    path("<slug:organization_slug>/collections/", views.collection_list, name="list"),
    path("<slug:organization_slug>/collections/new/", views.collection_create, name="create"),
]
