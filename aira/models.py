import csv
import datetime as dt
import math
import os
from collections import OrderedDict
from glob import iglob
from io import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import Http404
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

import swb
from hspatial import PointTimeseries, extract_point_from_raster
from osgeo import gdal

from .agrifield import AgrifieldSWBMixin, AgrifieldSWBResultsMixin

# notification_options is the list of options the user can select for
# notifications, e.g. be notified every day, every two days, every week, and so
# on. It is a dictionary; the key is an id of the option, and the value is a
# tuple whose first element is the human-readable description of an option,
# and the second element is a function receiving a single argument (normally
# the current date) and returning True if notifications are due in that
# particular date.

notification_options = OrderedDict(
    (
        ("D", (_("Daily"), lambda x: True)),
        ("2D", (_("Every two days"), lambda x: x.toordinal() % 2 == 0)),
        ("3D", (_("Every three days"), lambda x: x.toordinal() % 3 == 0)),
        ("4D", (_("Every four days"), lambda x: x.toordinal() % 4 == 0)),
        ("5D", (_("Every five days"), lambda x: x.toordinal() % 5 == 0)),
        ("7D", (_("Weekly"), lambda x: x.weekday() == 0)),
        ("10D", (_("Every ten days"), lambda x: x.day in (1, 11, 21))),
        ("30D", (_("Monthly"), lambda x: x.day == 1)),
    )
)


YES_OR_NO = ((True, _("Yes")), (False, _("No")))

YES_OR_NO_OR_NULL = ((True, _("Yes")), (False, _("No")), (None, "-"))

EMAIL_LANGUAGE_CHOICES = (("en", "English"), ("el", "Ελληνικά"))


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    notification = models.CharField(
        max_length=3,
        blank=True,
        default="",
        choices=[(x, notification_options[x][0]) for x in notification_options],
    )
    email_language = models.CharField(
        max_length=3,
        default=EMAIL_LANGUAGE_CHOICES[0][0],
        choices=EMAIL_LANGUAGE_CHOICES,
    )
    supervisor = models.ForeignKey(
        User, related_name="supervisor", null=True, blank=True, on_delete=models.CASCADE
    )
    supervision_question = models.BooleanField(choices=YES_OR_NO, default=False)

    class Meta:
        verbose_name_plural = "Profiles"

    def get_supervised(self):
        return Profile.objects.filter(supervisor=self.user)

    def __str__(self):
        return "UserProfile: {}".format(self.user)


@receiver(post_save, sender=User)
def create__or_update_user_profile(sender, instance, created, **kwargs):
    if not Profile.objects.filter(user=instance).exists():
        Profile.objects.create(user=instance)
    else:
        instance.profile.save()


class CropType(models.Model):
    name = models.CharField(max_length=100)
    root_depth_max = models.FloatField()
    root_depth_min = models.FloatField()
    max_allowed_depletion = models.FloatField()
    kc_plantingdate = models.FloatField()
    kc_offseason = models.FloatField(verbose_name="Kc off-season")
    planting_date = models.DateField()
    fek_category = models.IntegerField()

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Crop Types"

    def __str__(self):
        return str(self.name)

    @property
    def most_recent_planting_date(self):
        today = dt.date.today()
        result = self.planting_date.replace(year=today.year)
        if result <= today:
            return result
        return result.replace(year=today.year - 1)

    @property
    def kc_stages(self):
        result = []
        for kc_stage in self.croptypekcstage_set.order_by("order"):
            result.append(swb.KcStage(kc_stage.ndays, kc_stage.kc_end))
        return result

    @property
    def kc_stages_str(self):
        kc_stages = self.croptypekcstage_set.order_by("order")
        lines = [f"{s.ndays}\t{s.kc_end}" for s in kc_stages]
        return "\n".join(lines)


class KcStage(models.Model):
    order = models.PositiveSmallIntegerField()
    ndays = models.PositiveSmallIntegerField()
    kc_end = models.FloatField(
        validators=[MaxValueValidator(1.50), MinValueValidator(0.10)]
    )

    class Meta:
        abstract = True


class CropTypeKcStage(KcStage):
    crop_type = models.ForeignKey(CropType, on_delete=models.CASCADE)


class IrrigationType(models.Model):
    name = models.CharField(max_length=100)
    efficiency = models.FloatField()

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Irrigation Types"

    def __str__(self):
        return str(self.name)


class SoilAnalysisStorage(FileSystemStorage):
    def url(self, name):
        agrifield = Agrifield.objects.get(soil_analysis=name)
        return reverse("agrifield-soil-analysis", kwargs={"agrifield_id": agrifield.id})


class Agrifield(models.Model, AgrifieldSWBMixin, AgrifieldSWBResultsMixin):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, default="i.e. MyField1")
    is_virtual = models.NullBooleanField(
        choices=YES_OR_NO_OR_NULL, null=True, default=None
    )
    location = models.PointField()
    crop_type = models.ForeignKey(CropType, on_delete=models.CASCADE)
    irrigation_type = models.ForeignKey(IrrigationType, on_delete=models.CASCADE)
    area = models.FloatField()
    use_custom_parameters = models.BooleanField(default=False)
    custom_kc_offseason = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(1.50), MinValueValidator(0.10)],
    )
    custom_kc_plantingdate = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(1.50), MinValueValidator(0.10)],
    )
    custom_planting_date = models.DateField(null=True, blank=True)
    custom_root_depth_max = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(4.00), MinValueValidator(0.20)],
    )
    custom_root_depth_min = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(2.00), MinValueValidator(0.1)],
    )
    custom_max_allowed_depletion = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(0.99), MinValueValidator(0.00)],
    )
    custom_efficiency = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(1.00), MinValueValidator(0.05)],
    )
    custom_irrigation_optimizer = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(1.00), MinValueValidator(0.10)],
    )
    custom_field_capacity = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(0.45), MinValueValidator(0.10)],
    )
    custom_thetaS = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(0.55), MinValueValidator(0.30)],
    )
    custom_wilting_point = models.FloatField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(0.22), MinValueValidator(0.00)],
    )
    soil_analysis = models.FileField(
        blank=True, storage=SoilAnalysisStorage(), upload_to="soil_analyses"
    )

    @property
    def wilting_point(self):
        if self.use_custom_parameters and self.custom_wilting_point:
            return self.custom_wilting_point
        else:
            return self.default_wilting_point

    @property
    def default_wilting_point(self):
        if not self.in_covered_area:
            return None
        else:
            return extract_point_from_raster(
                self.location,
                gdal.Open(os.path.join(settings.AIRA_DATA_SOIL, "pwp.tif")),
            )

    @property
    def theta_s(self):
        if self.use_custom_parameters and self.custom_thetaS:
            return self.custom_thetaS
        else:
            return self.default_theta_s

    @property
    def default_theta_s(self):
        if not self.in_covered_area:
            return None
        else:
            return extract_point_from_raster(
                self.location,
                gdal.Open(os.path.join(settings.AIRA_DATA_SOIL, "theta_s.tif")),
            )

    @property
    def field_capacity(self):
        if self.use_custom_parameters and self.custom_field_capacity:
            return self.custom_field_capacity
        else:
            return self.default_field_capacity

    @property
    def default_field_capacity(self):
        if not self.in_covered_area:
            return None
        else:
            return extract_point_from_raster(
                self.location,
                gdal.Open(os.path.join(settings.AIRA_DATA_SOIL, "fc.tif")),
            )

    @property
    def irrigation_efficiency(self):
        if self.use_custom_parameters and self.custom_efficiency:
            return self.custom_efficiency
        else:
            return self.irrigation_type.efficiency

    @property
    def p(self):
        if self.use_custom_parameters and self.custom_max_allowed_depletion:
            return self.custom_max_allowed_depletion
        else:
            return self.crop_type.max_allowed_depletion

    @property
    def root_depth_max(self):
        if self.use_custom_parameters and self.custom_root_depth_max:
            return self.custom_root_depth_max
        else:
            return self.crop_type.root_depth_max

    @property
    def root_depth_min(self):
        if self.use_custom_parameters and self.custom_root_depth_min:
            return self.custom_root_depth_min
        else:
            return self.crop_type.root_depth_min

    @property
    def root_depth(self):
        return (self.root_depth_max + self.root_depth_min) / 2.0

    @property
    def irrigation_optimizer(self):
        if self.use_custom_parameters and self.custom_irrigation_optimizer:
            return self.custom_irrigation_optimizer
        else:
            return 0.5

    @property
    def last_irrigation(self):
        try:
            return self.appliedirrigation_set.latest()
        except AppliedIrrigation.DoesNotExist:
            return None

    def can_edit(self, user):
        if (user == self.owner) or (user == self.owner.profile.supervisor):
            return True
        raise Http404

    class Meta:
        ordering = ("name", "area")
        verbose_name_plural = "Agrifields"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super(Agrifield, self).save(*args, **kwargs)
        self._queue_for_calculation()
        self._delete_cached_point_timeseries()

    def _queue_for_calculation(self):
        from aira import tasks

        cache_key = "agrifield_{}_status".format(self.id)

        # If the agrifield is already in the Celery queue for calculation,
        # return without doing anything.
        if cache.get(cache_key) == "queued":
            return

        tasks.calculate_agrifield.delay(self)
        cache.set(cache_key, "queued", None)

    @property
    def status(self):
        return cache.get("agrifield_{}_status".format(self.id))

    @property
    def in_covered_area(self):
        mask = os.path.join(settings.AIRA_DATA_SOIL, "fc.tif")
        try:
            tmp_check = extract_point_from_raster(self.location, gdal.Open(mask))
        except (RuntimeError, ValueError):
            tmp_check = float("nan")
        return not math.isnan(tmp_check)

    def get_point_timeseries(self, variable):
        prefix = os.path.join(settings.AIRA_DATA_HISTORICAL, "daily_" + variable)
        dest = os.path.join(
            settings.AIRA_TIMESERIES_CACHE_DIR,
            "agrifield{}-{}.hts".format(self.id, variable),
        )
        PointTimeseries(
            point=self.location, prefix=prefix, default_time=dt.time(23, 59)
        ).get_cached(dest, version=2)
        return dest

    def _delete_cached_point_timeseries(self):
        filenamesglob = os.path.join(
            settings.AIRA_TIMESERIES_CACHE_DIR, "agrifield{}-*".format(self.id)
        )
        for filename in iglob(filenamesglob):
            os.remove(filename)

    def get_applied_irrigation_defaults(self):
        """
        Return a dict of all default values from the history of AppliedIrrigations.

        Note that some dict keys won't exist if no previous entries are found.
        """
        return {
            **self._get_applied_irrigation_default_type(),
            **self._get_applied_irrigation_defaults_for_volume(),
            **self._get_applied_irrigation_defaults_for_duration(),
            **self._get_applied_irrigation_defaults_for_flowmeter(),
        }

    def _get_applied_irrigation_default_type(self):
        try:
            return {
                "irrigation_type": self.appliedirrigation_set.latest().irrigation_type
            }
        except AppliedIrrigation.DoesNotExist:
            return {"irrigation_type": "VOLUME_OF_WATER"}

    def _get_applied_irrigation_defaults_for_volume(self):
        try:
            return {
                "supplied_water_volume": self.appliedirrigation_set.filter(
                    irrigation_type="VOLUME_OF_WATER"
                )
                .latest()
                .supplied_water_volume
            }
        except AppliedIrrigation.DoesNotExist:
            return {}

    def _get_applied_irrigation_defaults_for_duration(self):
        try:
            latest_entry = self.appliedirrigation_set.filter(
                irrigation_type="DURATION_OF_IRRIGATION"
            ).latest()
            return {
                "supplied_duration": latest_entry.supplied_duration,
                "supplied_flow_rate": latest_entry.supplied_flow_rate,
            }
        except AppliedIrrigation.DoesNotExist:
            return {}

    def _get_applied_irrigation_defaults_for_flowmeter(self):
        try:
            latest_entry = self.appliedirrigation_set.filter(
                irrigation_type="FLOWMETER_READINGS"
            ).latest()
            return {
                "flowmeter_water_percentage": latest_entry.flowmeter_water_percentage,
                "flowmeter_reading_start": latest_entry.flowmeter_reading_end,
            }
        except AppliedIrrigation.DoesNotExist:
            return {}

    def set_custom_kc_stages(self, s):
        """Replaces all existing kc stages with ones read from a string.

        The string can be comma-delimited or tab-delimited, or a mix.
        """

        s = s.replace("\t", ",")
        self.agrifieldcustomkcstage_set.all().delete()
        for i, row in enumerate(csv.reader(StringIO(s)), start=1):
            ndays = int(row[0])
            kc_end = float(row[1])
            AgrifieldCustomKcStage.objects.create(
                agrifield=self, order=i, ndays=ndays, kc_end=kc_end
            )

    @property
    def kc_stages_str(self):
        kc_stages = self.agrifieldcustomkcstage_set.order_by("order")
        lines = [f"{s.ndays}\t{s.kc_end}" for s in kc_stages]
        return "\n".join(lines)


class AgrifieldCustomKcStage(KcStage):
    agrifield = models.ForeignKey(Agrifield, on_delete=models.CASCADE)


class AppliedIrrigation(models.Model):

    IRRIGATION_TYPES = [
        ("VOLUME_OF_WATER", _("Volume of water")),
        ("DURATION_OF_IRRIGATION", _("Duration of irrigation")),
        ("FLOWMETER_READINGS", _("Flowmeter readings")),
    ]

    irrigation_type = models.CharField(
        max_length=50, choices=IRRIGATION_TYPES, default="VOLUME_OF_WATER"
    )
    agrifield = models.ForeignKey(Agrifield, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()

    supplied_water_volume = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0.0)]
    )

    supplied_duration = models.PositiveIntegerField(
        "Duration in minutes", null=True, blank=True
    )
    supplied_flow_rate = models.FloatField(
        "Flow rate (m3/h)", null=True, blank=True, validators=[MinValueValidator(0.0)]
    )

    flowmeter_reading_start = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0.0)]
    )
    flowmeter_reading_end = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0.0)]
    )
    flowmeter_water_percentage = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        default=100,
    )

    @property
    def volume(self):
        if self.irrigation_type == "VOLUME_OF_WATER":
            return self.supplied_water_volume

        try:
            # Wrapped in a try-except in case of null values exceptions
            if self.irrigation_type == "DURATION_OF_IRRIGATION":
                return (self.supplied_duration / 60) * self.supplied_flow_rate
            elif self.irrigation_type == "FLOWMETER_READINGS":
                difference = self.flowmeter_reading_end - self.flowmeter_reading_start
                return difference * (100 / self.flowmeter_water_percentage)
        except TypeError:
            return None

    @property
    def system_default_volume(self):
        # Can be used as a fallback whenever no volume is associated with the instance.
        return (
            float(self.agrifield.p)
            * (self.agrifield.field_capacity - self.agrifield.wilting_point)
            * self.agrifield.root_depth
            * self.agrifield.area
        )

    class Meta:
        get_latest_by = "timestamp"
        ordering = ("-timestamp",)

    def __str__(self):
        return str(self.timestamp)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.agrifield._queue_for_calculation()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.agrifield._queue_for_calculation()
