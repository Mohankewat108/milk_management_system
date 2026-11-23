from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("parties", "0003_farmer_invitation"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="farmerinvitation",
            old_name="parties_far_org_fa_7ee1f0_idx",
            new_name="parties_far_organiz_2b2f92_idx",
        ),
        migrations.RenameIndex(
            model_name="farmerinvitation",
            old_name="parties_far_org_em_9f1cf8_idx",
            new_name="parties_far_organiz_fb0922_idx",
        ),
        migrations.AlterField(
            model_name="farmerinvitation",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
