import apps.data_exports.storage
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("data_exports", "0002_export_templates_schedules_imports")]

    operations = [
        migrations.AlterField(
            model_name="exportjob",
            name="file",
            field=models.FileField(blank=True, storage=apps.data_exports.storage.PrivateFileSystemStorage(), upload_to="private_exports/%Y/%m/"),
        ),
        migrations.AlterField(
            model_name="importbatch",
            name="file",
            field=models.FileField(storage=apps.data_exports.storage.PrivateFileSystemStorage(), upload_to="private_imports/%Y/%m/"),
        ),
    ]
