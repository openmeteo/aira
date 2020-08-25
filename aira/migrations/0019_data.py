"""Create (and delete) crop types and irrigation types.

Crop types and irrigation types had been created by fixtures, which were a pain and were
creating problems, so we have abolished them.

However, new installations (including dev installations and unit testing), need these
crop types and irrigation types to be created, so we create them in this migration, only
if they do not already exist.

At the same time, we remove crop types that had been created by the fixtures and which
we no longer use.
"""
import os
from io import StringIO

from django.core.management import call_command
from django.db import connection, migrations

crop_types = [
    {
        "pk": 4,
        "max_allow_depletion": "0.35",
        "kc": 0.8,
        "root_depth_max": 1.3,
        "name": "Ακτινίδιο (Kiwi)",
        "root_depth_min": 0.7,
        "fek_category": 6,
    },
    {
        "pk": 15,
        "kc": 0.55,
        "root_depth_max": 1.7,
        "root_depth_min": 1.2,
        "name": "Ελιά (40 ως 60% κάλυψη εδάφους) "
        "(Olives (40 to 60% ground coverage by canopy))",
        "fek_category": 1,
        "max_allow_depletion": "0.65",
    },
    {
        "pk": 16,
        "root_depth_min": 0.8,
        "name": "Εσπεριδοειδή - 20% κάλυψη εδάφους (Citrus - 20% Canopy)",
        "root_depth_max": 1.1,
        "kc": 0.55,
        "fek_category": 1,
        "max_allow_depletion": "0.50",
    },
    {
        "pk": 17,
        "root_depth_min": 1.1,
        "name": "Εσπεριδοειδή - 50% κάλυψη εδάφους (Citrus - 50% Canopy)",
        "root_depth_max": 1.5,
        "kc": 0.55,
        "fek_category": 1,
        "max_allow_depletion": "0.50",
    },
    {
        "pk": 18,
        "max_allow_depletion": "0.50",
        "root_depth_min": 1.2,
        "name": "Εσπεριδοειδή - 70% κάλυψη εδάφους (Citrus - 70% Canopy)",
        "root_depth_max": 1.5,
        "kc": 0.55,
        "fek_category": 1,
    },
    {
        "root_depth_max": 1,
        "kc": 0.85,
        "name": "Χλοοτάπητας θερμόφιλλος (Turf grass - warm session )",
        "root_depth_min": 0.5,
        "fek_category": 6,
        "max_allow_depletion": "0.50",
        "pk": 73,
    },
    {
        "pk": 74,
        "kc": 0.95,
        "root_depth_max": 1,
        "root_depth_min": 0.5,
        "name": "Χλοοτάπητας ψυχρόφιλος (Turf grass - cool season)",
        "fek_category": 6,
        "max_allow_depletion": "0.40",
    },
]

irrigation_types = [
    {"efficiency": 0.6, "name": "Επιφανειακή άρδευση (Surface irrigation)", "pk": 1},
    {"efficiency": 0.75, "name": "Καταιονισμός (Sprinkler irrigation)", "pk": 2},
    {"name": "Μικροεκτοξευτήρες (Micro sprinklers)", "efficiency": 0.8, "pk": 3},
    {"pk": 4, "efficiency": 0.9, "name": "Άρδευση με σταγόνες (Drip irrigation)"},
    {
        "pk": 5,
        "efficiency": 0.95,
        "name": "Υπόγεια στάγδην άρδευση (Subsurface drip irrigation)",
    },
]


def create_crop_types(apps, schema_editor):
    CropType = apps.get_model("aira", "CropType")
    for ct in crop_types:
        if not CropType.objects.filter(pk=ct["pk"]).exists():
            CropType.objects.create(**ct)
    _reset_id_sequence("aira_croptype")


def create_irrigation_types(apps, schema_editor):
    IrrigationType = apps.get_model("aira", "IrrigationType")
    for it in irrigation_types:
        if not IrrigationType.objects.filter(pk=it["pk"]).exists():
            IrrigationType.objects.create(**it)
    _reset_id_sequence("aira_irrigationtype")


def remove_obsolete_crop_types(apps, schema_editor):
    crop_types_to_keep = [crop["pk"] for crop in crop_types]
    _verify_crop_types_can_be_removed(apps, schema_editor, crop_types_to_keep)
    _do_crop_type_removal(apps, schema_editor, crop_types_to_keep)


def _verify_crop_types_can_be_removed(apps, schema_editor, crop_types_to_keep):
    Agrifield = apps.get_model("aira", "Agrifield")
    offending_agrifields = Agrifield.objects.exclude(
        crop_type_id__in=crop_types_to_keep
    ).order_by("id")
    if offending_agrifields.exists():
        ids = ", ".join([str(agrifield.id) for agrifield in offending_agrifields])
        raise RuntimeError(
            "Can't remove crop types; some agrifields have a crop type that would be "
            "removed. Remove or change these agrifields first. The ids of the "
            "offending agrifields are " + ids
        )


def _do_crop_type_removal(apps, schema_editor, crop_types_to_keep):
    CropType = apps.get_model("aira", "CropType")
    CropType.objects.exclude(id__in=crop_types_to_keep).delete()


def _reset_id_sequence(table_name):
    saved_django_colors = os.environ.get("DJANGO_COLORS", "")
    try:
        os.environ["DJANGO_COLORS"] = "nocolor"
        commands = StringIO()
        call_command("sqlsequencereset", "aira", stdout=commands)
        commands.seek(0)
        for line in commands:
            if f'"{table_name}"' in line:
                connection.cursor().execute(line)
    finally:
        os.environ["DJANGO_COLORS"] = saved_django_colors


class Migration(migrations.Migration):

    dependencies = [("aira", "0018_agrifield_profile_additions")]

    operations = [
        migrations.RunPython(create_crop_types, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(
            create_irrigation_types, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            remove_obsolete_crop_types, reverse_code=migrations.RunPython.noop
        ),
    ]
