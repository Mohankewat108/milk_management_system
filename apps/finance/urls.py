from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("<slug:organization_slug>/payments/", views.payment_list, name="list"),
    path("<slug:organization_slug>/payments/new/", views.payment_create, name="create"),
    path("<slug:organization_slug>/payments/<uuid:payment_id>/complete/", views.payment_complete, name="complete"),
]
