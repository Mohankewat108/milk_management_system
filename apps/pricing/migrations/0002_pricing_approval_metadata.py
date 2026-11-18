import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("pricing", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="pricingconfiguration", name="approved_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="approved_pricing_configurations", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="pricingconfiguration", name="approved_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="pricingconfiguration", name="notes", field=models.CharField(blank=True, max_length=240)),
        migrations.AddIndex(model_name="pricingconfiguration", index=models.Index(fields=["organization", "effective_from", "effective_to"], name="pricing_org_dates_idx")),
        migrations.AddIndex(model_name="pricingconfiguration", index=models.Index(fields=["organization", "branch", "is_approved"], name="pricing_scope_active_idx")),
    ]
