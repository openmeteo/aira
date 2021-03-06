# Generated by Django 2.2.2 on 2019-08-10 14:43

from django.contrib.gis.db.models.fields import PointField
from django.contrib.gis.geos import Point
from django.db import migrations
from django.db.models import FloatField


def latlon2point(apps, schema_editor):
    Agrifield = apps.get_model("aira", "Agrifield")
    for agrifield in Agrifield.objects.all():
        agrifield.location = Point(agrifield.longitude, agrifield.latitude)
        agrifield.save()


def point2latlon(apps, schema_editor):
    Agrifield = apps.get_model("aira", "Agrifield")
    for agrifield in Agrifield.objects.all():
        agrifield.latitude = agrifield.location.y
        agrifield.longitude = agrifield.location.x
        agrifield.save()


class Migration(migrations.Migration):

    dependencies = [("aira", "0021_lint")]

    operations = [
        migrations.AddField(
            model_name="agrifield", name="location", field=PointField(null=True)
        ),
        migrations.AlterField(
            model_name="agrifield", name="latitude", field=FloatField(null=True)
        ),
        migrations.AlterField(
            model_name="agrifield", name="longitude", field=FloatField(null=True)
        ),
        migrations.RunPython(latlon2point, point2latlon),
        migrations.RemoveField(model_name="agrifield", name="latitude"),
        migrations.RemoveField(model_name="agrifield", name="longitude"),
        migrations.AlterField(
            model_name="agrifield", name="location", field=PointField(null=False)
        ),
    ]
