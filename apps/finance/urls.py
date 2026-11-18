from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("<slug:organization_slug>/payments/", views.payment_list, name="list"),
    path("<slug:organization_slug>/payments/new/", views.payment_create, name="create"),
    path("<slug:organization_slug>/payments/<uuid:payment_id>/edit/", views.payment_edit, name="edit"),
    path("<slug:organization_slug>/payments/<uuid:payment_id>/complete/", views.payment_complete, name="complete"),
    path("<slug:organization_slug>/expenses/", views.expense_list, name="expenses"),
    path("<slug:organization_slug>/expenses/new/", views.expense_create, name="expense_create"),
    path("<slug:organization_slug>/expenses/<uuid:expense_id>/edit/", views.expense_edit, name="expense_edit"),
    path("<slug:organization_slug>/expenses/<uuid:expense_id>/approve/", views.expense_approve, name="expense_approve"),
]
