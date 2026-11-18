# Generated for additive milk quality capture fields.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("collections", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="milkcollection",
            name="lactometer_reading",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name="milkcollection",
            name="milk_temperature_c",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name="milkcollection",
            name="sample_reference",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="milkcollection",
            name="quality_test_method",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="milkcollection",
            name="tested_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tested_milk_collections", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name="milkcollection",
            constraint=models.CheckConstraint(condition=models.Q(("lactometer_reading__isnull", True), ("lactometer_reading__gte", 0), _connector="OR"), name="collection_lactometer_nonnegative"),
        ),
        migrations.AddIndex(
            model_name="milkcollection",
            index=models.Index(fields=["customer", "collected_at"], name="coll_customer_date_idx"),
        ),
    ]
