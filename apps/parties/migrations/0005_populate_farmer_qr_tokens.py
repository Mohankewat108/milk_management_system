from uuid import uuid4
from django.db import migrations, models

def populate_tokens(apps, schema_editor):
    Farmer = apps.get_model("parties", "Farmer")
    for farmer in Farmer.objects.filter(qr_token__isnull=True).iterator():
        farmer.qr_token = uuid4()
        farmer.save(update_fields=["qr_token"])

class Migration(migrations.Migration):
    dependencies = [("parties", "0004_farmer_qr_token")]
    operations = [
        migrations.RunPython(populate_tokens, migrations.RunPython.noop),
        migrations.AlterField(model_name="farmer", name="qr_token", field=models.UUIDField(default=uuid4, unique=True, editable=False, db_index=True)),
    ]
