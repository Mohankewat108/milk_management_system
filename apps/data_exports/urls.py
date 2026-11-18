from django.urls import path

from . import advanced_views, views

app_name = "data_exports"

urlpatterns = [
    path("<slug:organization_slug>/exports/", views.export_centre, name="centre"),
    path("<slug:organization_slug>/exports/<str:module>/queue/", views.queue_export_view, name="queue"),
    path("<slug:organization_slug>/exports/jobs/<uuid:job_id>/download/", views.download_export, name="download"),
    path("<slug:organization_slug>/exports/templates/save/", advanced_views.save_export_template, name="template_save"),
    path("<slug:organization_slug>/exports/schedules/create/", advanced_views.create_schedule, name="schedule_create"),
    path("<slug:organization_slug>/exports/schedules/<uuid:schedule_id>/toggle/", advanced_views.toggle_schedule, name="schedule_toggle"),
    path("<slug:organization_slug>/imports/upload/", advanced_views.upload_import, name="import_upload"),
    path("<slug:organization_slug>/imports/sample/<str:module>/", advanced_views.import_sample, name="import_sample"),
    path("<slug:organization_slug>/reports/", advanced_views.reports_dashboard, name="reports"),
    path("<slug:organization_slug>/bulk/<str:module>/", advanced_views.bulk_party_action, name="bulk_party"),
]
