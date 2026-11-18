from django.urls import path

from . import views

app_name = "data_exports"

urlpatterns = [
    path("<slug:organization_slug>/exports/", views.export_centre, name="centre"),
    path("<slug:organization_slug>/exports/<str:module>/csv/", views.export_csv, name="csv"),
    path("<slug:organization_slug>/exports/jobs/<uuid:job_id>/download/", views.download_export, name="download"),
]
