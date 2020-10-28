import datetime as dt
import os
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.http.response import Http404
from django.test import TestCase, override_settings

from model_mommy import mommy
from swb import KcStage

from aira import models
from aira.tests import RandomMediaRootMixin


class UserTestCase(TestCase):
    def setUp(self):
        self.assertEqual(models.Profile.objects.count(), 0)
        self.user = User.objects.create_user(
            id=55, username="bob", password="topsecret"
        )

    def test_create_user_profile_receiver(self):
        self.assertEqual(hasattr(self.user, "profile"), True)

    def test_created_user_same_profile_FK(self):
        profile = models.Profile.objects.get(user_id=self.user.id)
        self.assertEqual(profile.user, self.user)

    def test_save_user_profile_receiver(self):
        self.user.profile.first_name = "Bruce"
        self.user.profile.last_name = "Wayne"
        self.user.profile.address = "Gotham City"
        self.user.save()
        profile = models.Profile.objects.get(user_id=self.user.id)
        self.assertEqual(profile.first_name, "Bruce")
        self.assertEqual(profile.last_name, "Wayne")
        self.assertEqual(profile.address, "Gotham City")


class AgrifieldTestCaseBase(TestCase):
    def setUp(self):
        self.crop_type = mommy.make(
            models.CropType,
            name="Grass",
            root_depth_max=0.7,
            root_depth_min=1.2,
            max_allowed_depletion=0.5,
            fek_category=4,
        )
        self.irrigation_type = mommy.make(
            models.IrrigationType, name="Surface irrigation", efficiency=0.60
        )
        self.user = User.objects.create_user(
            id=55, username="bob", password="topsecret"
        )
        self.agrifield = mommy.make(
            models.Agrifield,
            id=42,
            owner=self.user,
            name="A field",
            crop_type=self.crop_type,
            irrigation_type=self.irrigation_type,
            location=Point(18.0, 23.0),
            area=2000,
        )


class AgrifieldTestCase(AgrifieldTestCaseBase):
    def test_agrifield_creation(self):
        agrifield = models.Agrifield.objects.create(
            owner=self.user,
            name="A field",
            crop_type=self.crop_type,
            irrigation_type=self.irrigation_type,
            location=Point(18.0, 23.0),
            area=2000,
        )
        self.assertTrue(isinstance(agrifield, models.Agrifield))
        self.assertEqual(agrifield.__str__(), agrifield.name)

    def test_agrifield_update(self):
        self.agrifield.name = "This another field name"
        self.agrifield.save()
        self.assertEqual(self.agrifield.__str__(), "This another field name")

    def test_agrifield_delete(self):
        self.agrifield.delete()
        self.assertEqual(models.Agrifield.objects.all().count(), 0)

    def test_valid_user_can_edit(self):
        self.assertTrue(self.agrifield.can_edit(self.user))

    def test_invalid_user_cannot_edit(self):
        user = User.objects.create_user(id=56, username="charlie", password="topsecret")
        with self.assertRaises(Http404):
            self.agrifield.can_edit(user)

    def test_agrifield_irrigation_optimizer_default_value(self):
        self.assertEqual(self.agrifield.irrigation_optimizer, 0.5)

    def test_agrifield_use_custom_parameters_default_value(self):
        self.assertFalse(self.agrifield.use_custom_parameters)


class AgrifieldDeletesCachedPointTimeseriesOnSave(AgrifieldTestCaseBase):
    def setUp(self):
        super().setUp()
        self.tmpdir = tempfile.mkdtemp()
        self._create_test_files()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        super().tearDown()

    def _create_test_files(self):
        self.relevant_pathname = self._create_test_file("agrifield42-temperature.hts")
        self.irrelevant_pathname = self._create_test_file(
            "agrifield425-temperature.hts"
        )

    def _create_test_file(self, filename):
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w") as f:
            f.write("hello world")
        return path

    def test_cached_point_timeseries_is_deleted_on_save(self):
        assert os.path.exists(self.relevant_pathname)
        with override_settings(AIRA_TIMESERIES_CACHE_DIR=self.tmpdir):
            self.agrifield.save()
        self.assertFalse(os.path.exists(self.relevant_pathname))

    def test_irrelevant_cached_point_timeseries_is_untouched(self):
        with override_settings(AIRA_TIMESERIES_CACHE_DIR=self.tmpdir):
            self.agrifield.save()
        self.assertTrue(os.path.exists(self.irrelevant_pathname))


class AgrifieldSoilAnalysisTestCase(TestCase, RandomMediaRootMixin):
    def setUp(self):
        self.override_media_root()
        self.agrifield = mommy.make(models.Agrifield)
        self.agrifield.soil_analysis.save("somefile", ContentFile("hello world"))

    def tearDown(self):
        self.end_media_root_override()

    def test_file_data(self):
        with open(self.agrifield.soil_analysis.path, "r") as f:
            self.assertEqual(f.read(), "hello world")

    def test_file_url(self):
        self.assertEqual(
            self.agrifield.soil_analysis.url,
            "/agrifield/{}/soil_analysis/".format(self.agrifield.id),
        )


class CropTypeMostRecentPlantingDateTestCase(TestCase):
    def setUp(self):
        self.crop_type = mommy.make(
            models.CropType, planting_date=dt.datetime(1971, 3, 15)
        )

    @mock.patch("aira.models.dt.date")
    def test_result_when_it_has_appeared_this_year(self, m):
        m.today.return_value = dt.datetime(2019, 3, 20)
        m.side_effect = lambda *args, **kwargs: dt.date(*args, **kwargs)
        self.assertEqual(
            self.crop_type.most_recent_planting_date, dt.datetime(2019, 3, 15)
        )

    @mock.patch("aira.models.dt.date")
    def test_result_when_it_has_not_appeared_this_year_yet(self, m):
        m.today.return_value = dt.datetime(2019, 3, 10)
        m.side_effect = lambda *args, **kwargs: dt.date(*args, **kwargs)
        self.assertEqual(
            self.crop_type.most_recent_planting_date, dt.datetime(2018, 3, 15)
        )


class CropTypeKcStagesTestCase(TestCase):
    def setUp(self):
        self.crop_type = mommy.make(
            models.CropType,
            planting_date=dt.datetime(1971, 3, 21),
            kc_offseason=0.3,
            kc_plantingdate=0.7,
        )
        for i, s in enumerate([(35, 0.7), (45, 1.05), (40, 1.05), (15, 0.95)], start=1):
            models.CropTypeKcStage.objects.create(
                crop_type=self.crop_type, order=i, ndays=s[0], kc_end=s[1]
            )

    def test_kc_stages(self):
        self.assertEqual(
            self.crop_type.kc_stages,
            [
                KcStage(35, 0.7),
                KcStage(45, 1.05),
                KcStage(40, 1.05),
                KcStage(15, 0.95),
            ],
        )

    def test_kc_stages_str(self):
        self.assertEqual(
            self.crop_type.kc_stages_str, "35\t0.7\n45\t1.05\n40\t1.05\n15\t0.95"
        )


class AgrifieldLatestAppliedIrrigationDefaultsTestCase(TestCase):
    def setUp(self):
        self.agrifield = mommy.make(models.Agrifield)

    def test_no_applied_irrigations_present(self):
        defaults = self.agrifield.get_applied_irrigation_defaults()
        self.assertEqual(defaults, {"irrigation_type": "VOLUME_OF_WATER"})

    def test_default_irrigation_type_and_all_values_present(self):
        latest = dt.datetime(2020, 3, 1, 0, 0, tzinfo=dt.timezone.utc)

        # To assert which instance is the value coming from, a simple 2 digits scheme
        # is followed, first digit is the field id, the second is a bit (T/F)
        mommy.make(
            models.AppliedIrrigation,
            agrifield=self.agrifield,
            irrigation_type="VOLUME_OF_WATER",
            timestamp=latest - dt.timedelta(days=1),
            supplied_water_volume=11,
            supplied_duration=20,
            supplied_flow_rate=30,
            flowmeter_reading_end=40,
            flowmeter_water_percentage=50,
            flowmeter_reading_start=60,
        )
        mommy.make(
            models.AppliedIrrigation,
            agrifield=self.agrifield,
            irrigation_type="FLOWMETER_READINGS",
            timestamp=latest,
            supplied_water_volume=10,
            supplied_duration=20,
            supplied_flow_rate=30,
            flowmeter_reading_end=41,
            flowmeter_water_percentage=51,
            flowmeter_reading_start=61,  # Won't be used anyway (end=start)
        )
        mommy.make(
            models.AppliedIrrigation,
            agrifield=self.agrifield,
            irrigation_type="DURATION_OF_IRRIGATION",
            timestamp=latest - dt.timedelta(days=5),
            supplied_water_volume=10,
            supplied_duration=21,
            supplied_flow_rate=31,
            flowmeter_reading_end=40,
            flowmeter_water_percentage=50,
            flowmeter_reading_start=60,
        )
        defaults = self.agrifield.get_applied_irrigation_defaults()
        expected_defaults = {
            "irrigation_type": "FLOWMETER_READINGS",
            "supplied_water_volume": 11.0,
            "supplied_duration": 21,
            "supplied_flow_rate": 31.0,
            "flowmeter_reading_start": 41.0,
            "flowmeter_water_percentage": 51,
        }
        self.assertEqual(defaults, expected_defaults)

    def test_only_water_volume_default_present(self):
        mommy.make(
            models.AppliedIrrigation,
            agrifield=self.agrifield,
            irrigation_type="VOLUME_OF_WATER",
            timestamp=dt.datetime(2020, 3, 1, 0, 0, tzinfo=dt.timezone.utc),
            supplied_water_volume=1337,
        )
        defaults = self.agrifield.get_applied_irrigation_defaults()
        expected_defaults = {
            "irrigation_type": "VOLUME_OF_WATER",
            "supplied_water_volume": 1337,
        }
        self.assertEqual(defaults, expected_defaults)


class AgrifieldCustomKcStagesTestCase(TestCase):
    def setUp(self):
        self.agrifield = mommy.make(models.Agrifield)
        csv = "15,0.9\n25\t0.8"
        self.agrifield.set_custom_kc_stages(csv)

    def test_set_custom_kc_stages(self):
        kc_stages = models.AgrifieldCustomKcStage.objects.order_by("order")
        self.assertEqual(kc_stages[0].order, 1)
        self.assertEqual(kc_stages[0].ndays, 15)
        self.assertAlmostEqual(kc_stages[0].kc_end, 0.9)
        self.assertEqual(kc_stages[1].order, 2)
        self.assertEqual(kc_stages[1].ndays, 25)
        self.assertAlmostEqual(kc_stages[1].kc_end, 0.8)

    def test_kc_stages_str(self):
        self.assertEqual(self.agrifield.kc_stages_str, "15\t0.9\n25\t0.8")


class AppliedIrrigationTestCase(TestCase):
    def setUp(self):
        # Populate the rest to assure that the correct value is the one
        # being used for calculation according to 'irrigation_type'
        self.defaults = {
            "supplied_water_volume": 100,
            "supplied_duration": 100,
            "supplied_flow_rate": 100,
            "flowmeter_reading_start": 100,
            "flowmeter_reading_end": 100,
            "flowmeter_water_percentage": 100,
        }

    def test_calculated_volume_supplied_water_volume(self):
        kwargs = {
            **self.defaults,
            "supplied_water_volume": 1337,
        }
        irrigation = mommy.make(
            models.AppliedIrrigation, irrigation_type="VOLUME_OF_WATER", **kwargs
        )
        self.assertEqual(irrigation.volume, 1337)

    def test_calculated_volume_supplied_duration(self):
        kwargs = {
            **self.defaults,
            "supplied_duration": 1337 * 60 * 2,
            "supplied_flow_rate": 0.5,
        }
        irrigation = mommy.make(
            models.AppliedIrrigation, irrigation_type="DURATION_OF_IRRIGATION", **kwargs
        )
        self.assertEqual(irrigation.volume, 1337)

    def test_calculated_volume_supplied_flowmeter_readings(self):
        kwargs = {
            **self.defaults,
            "flowmeter_reading_start": 1000,
            "flowmeter_reading_end": 1000 + 1337,
            "flowmeter_water_percentage": 50,
        }
        irrigation = mommy.make(
            models.AppliedIrrigation, irrigation_type="FLOWMETER_READINGS", **kwargs
        )
        self.assertEqual(irrigation.volume, 1337 * 2)  # Double; since percentage is 50%

    def test_calculated_volume_with_no_values_recorded(self):
        types = ["VOLUME_OF_WATER", "DURATION_OF_IRRIGATION", "FLOWMETER_READINGS"]
        for ir_type in types:
            irrigation = mommy.make(
                models.AppliedIrrigation, irrigation_type="DURATION_OF_IRRIGATION"
            )
            self.assertIsNone(irrigation.volume)
