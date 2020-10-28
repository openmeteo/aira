import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError


def populate_kc_offseason(apps, schema_editor):
    CropType = apps.get_model("aira", "CropType")
    for crop_type in CropType.objects.all():
        crop_type.kc_offseason = crop_type.kc_initial
        crop_type.save()


def do_nothing(apps, schema_editor):
    pass


def populate_croptypekcstage(apps, schema_editor):
    CropType = apps.get_model("aira", "CropType")
    CropTypeKcStage = apps.get_model("aira", "CropTypeKcStage")
    for crop_type in CropType.objects.all():
        crop_type.kc_offseason = crop_type.kc_initial
        kc_initial = crop_type.kc_initial
        if kc_initial == crop_type.kc_mid and kc_initial == crop_type.kc_end:
            continue
        CropTypeKcStage.objects.create(
            crop_type=crop_type,
            order=1,
            ndays=crop_type.days_kc_init,
            kc_end=crop_type.kc_initial,
        )
        CropTypeKcStage.objects.create(
            crop_type=crop_type,
            order=2,
            ndays=crop_type.days_kc_dev,
            kc_end=crop_type.kc_mid,
        )
        CropTypeKcStage.objects.create(
            crop_type=crop_type,
            order=3,
            ndays=crop_type.days_kc_mid,
            kc_end=crop_type.kc_mid,
        )
        CropTypeKcStage.objects.create(
            crop_type=crop_type,
            order=4,
            ndays=crop_type.days_kc_late,
            kc_end=crop_type.kc_end,
        )


def revert_croptypekcstage(apps, schema_editor):
    CropType = apps.get_model("aira", "CropType")
    CropTypeKcStage = apps.get_model("aira", "CropTypeKcStage")
    for crop_type in CropType.objects.all():
        stages = CropTypeKcStage.objects.filter(crop_type=crop_type).order_by("order")
        ndays = [stage.ndays for stage in stages]
        kc = [stage.kc_end for stage in stages]
        if len(kc) == 0:
            crop_type.kc_mid = crop_type.kc_initial
            crop_type.kc_end = crop_type.kc_initial
            crop_type.days_kc_init = 42
            crop_type.days_kc_dev = 42
            crop_type.days_kc_mid = 42
            crop_type.days_kc_late = 42
        elif len(kc) == 4 and kc[0] == crop_type.kc_initial and kc[1] == kc[2]:
            crop_type.kc_mid = kc[1]
            crop_type.kc_end = kc[3]
            crop_type.days_kc_init = ndays[0]
            crop_type.days_kc_dev = ndays[1]
            crop_type.days_kc_mid = ndays[2]
            crop_type.days_kc_late = ndays[3]
        else:
            raise IrreversibleError(
                f"Can't determine kc parameters for crop_type.id={crop_type.id}"
            )
        crop_type.save()


class Migration(migrations.Migration):

    dependencies = [
        ("aira", "0030_applied_irrigation_types"),
    ]

    operations = [
        migrations.RenameField(
            model_name="agrifield", old_name="custom_kc", new_name="custom_kc_initial"
        ),
        migrations.RenameField(
            model_name="croptype", old_name="kc_init", new_name="kc_initial"
        ),
        migrations.AddField(
            model_name="croptype",
            name="kc_offseason",
            field=models.FloatField(null=True, verbose_name="Kc off-season"),
        ),
        migrations.AddField(
            model_name="agrifield",
            name="custom_kc_offseason",
            field=models.FloatField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MaxValueValidator(1.5),
                    django.core.validators.MinValueValidator(0.1),
                ],
            ),
        ),
        migrations.AddField(
            model_name="agrifield",
            name="custom_planting_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="CropTypeKcStage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveSmallIntegerField()),
                ("ndays", models.PositiveSmallIntegerField()),
                (
                    "kc_end",
                    models.FloatField(
                        validators=[
                            django.core.validators.MaxValueValidator(1.5),
                            django.core.validators.MinValueValidator(0.1),
                        ]
                    ),
                ),
                (
                    "crop_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="aira.CropType"
                    ),
                ),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="AgrifieldCustomKcStage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveSmallIntegerField()),
                ("ndays", models.PositiveSmallIntegerField()),
                (
                    "kc_end",
                    models.FloatField(
                        validators=[
                            django.core.validators.MaxValueValidator(1.5),
                            django.core.validators.MinValueValidator(0.1),
                        ]
                    ),
                ),
                (
                    "agrifield",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="aira.Agrifield"
                    ),
                ),
            ],
            options={"abstract": False},
        ),
        migrations.AlterField(
            model_name="croptype",
            name="days_kc_init",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="croptype",
            name="days_kc_dev",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="croptype",
            name="days_kc_mid",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="croptype",
            name="days_kc_late",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="croptype",
            name="kc_end",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="croptype",
            name="kc_mid",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.RunPython(populate_kc_offseason, do_nothing),
        migrations.RunPython(populate_croptypekcstage, revert_croptypekcstage),
        migrations.AlterField(
            model_name="croptype",
            name="kc_offseason",
            field=models.FloatField(null=False, verbose_name="Kc off-season"),
        ),
        migrations.RemoveField(model_name="croptype", name="days_kc_dev"),
        migrations.RemoveField(model_name="croptype", name="days_kc_init"),
        migrations.RemoveField(model_name="croptype", name="days_kc_late"),
        migrations.RemoveField(model_name="croptype", name="days_kc_mid"),
        migrations.RemoveField(model_name="croptype", name="kc_end"),
        migrations.RemoveField(model_name="croptype", name="kc_mid"),
    ]
