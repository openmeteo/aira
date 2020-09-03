from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("aira", "0028_custom_max_allowed_depletion__lte__0_99"),
    ]

    operations = [
        migrations.RenameModel("IrrigationLog", "AppliedIrrigation"),
        migrations.AlterModelOptions(
            name="appliedirrigation",
            options={"get_latest_by": "timestamp", "ordering": ("-timestamp",)},
        ),
        migrations.RenameField(
            model_name="appliedirrigation", old_name="time", new_name="timestamp"
        ),
        migrations.RenameField(
            model_name="appliedirrigation",
            old_name="applied_water",
            new_name="supplied_water_volume",
        ),
    ]
