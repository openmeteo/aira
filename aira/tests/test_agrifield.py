import datetime as dt
import os
import shutil
import tempfile
from glob import glob
from unittest.mock import PropertyMock, patch

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.test import TestCase, override_settings

import numpy as np
import pandas as pd
from freezegun import freeze_time
from model_mommy import mommy
from osgeo import gdal, osr

from aira import models
from aira.agrifield import InitialConditions


def setup_input_file(filename, value, timestamp_str):
    """Save value, which is an np array, to a GeoTIFF file."""
    nodata = 1e8
    value[np.isnan(value)] = nodata
    f = gdal.GetDriverByName("GTiff").Create(filename, 2, 2, 1, gdal.GDT_Float32)
    try:
        timestamp_str = timestamp_str or "1970-01-01"
        f.SetMetadataItem("TIMESTAMP", timestamp_str)
        f.SetGeoTransform((22.0, 0.01, 0, 38.0, 0, -0.01))
        wgs84 = osr.SpatialReference()
        wgs84.ImportFromEPSG(4326)
        f.SetProjection(wgs84.ExportToWkt())
        f.GetRasterBand(1).SetNoDataValue(nodata)
        f.GetRasterBand(1).WriteArray(value)
    finally:
        f = None


class SetupTestDataMixin:
    @classmethod
    def _setup_rasters(cls):
        cls._setup_field_capacity_raster()
        cls._setup_draintime_rasters()
        cls._setup_theta_s_raster()
        cls._setup_pwp_raster()
        cls._setup_meteo_rasters()

    @classmethod
    def _setup_field_capacity_raster(cls):
        filename = os.path.join(cls.tempdir, "fc.tif")
        setup_input_file(filename, np.array([[0.4, 0.45], [0.50, 0.55]]), None)

    @classmethod
    def _setup_draintime_rasters(cls):
        filename = os.path.join(cls.tempdir, "a_1d.tif")
        setup_input_file(filename, np.array([[30, 30], [30, 30]]), None)
        filename = os.path.join(cls.tempdir, "b.tif")
        setup_input_file(filename, np.array([[0.95, 0.95], [0.95, 0.95]]), None)

    @classmethod
    def _setup_theta_s_raster(cls):
        filename = os.path.join(cls.tempdir, "theta_s.tif")
        setup_input_file(filename, np.array([[0.5, 0.51], [0.52, 0.53]]), None)

    @classmethod
    def _setup_pwp_raster(cls):
        filename = os.path.join(cls.tempdir, "pwp.tif")
        setup_input_file(filename, np.array([[0.1, 0.15], [0.2, 0.25]]), None)

    @classmethod
    def _setup_meteo_rasters(cls):
        cls._setup_test_raster("rain", "2018-03-15", [[0.0, 0.1], [0.2, 0.3]])
        cls._setup_test_raster("evaporation", "2018-03-15", [[70, 2.2], [2.3, 2.4]])
        cls._setup_test_raster("rain", "2018-03-16", [[5.0, 0.6], [0.7, 0.8]])
        cls._setup_test_raster("evaporation", "2018-03-16", [[70, 9.2], [9.3, 9.4]])
        cls._setup_test_raster("rain", "2018-03-17", [[5.0, 0.5], [0.6, 0.7]])
        cls._setup_test_raster("evaporation", "2018-03-17", [[5, 9.6], [9.7, 9.8]])
        cls._setup_test_raster("rain", "2018-03-18", [[0.3, 0.2], [0.1, 0.0]])
        cls._setup_test_raster("evaporation", "2018-03-18", [[70, 9.7], [9.8, 9.9]])
        cls._setup_test_raster("rain", "2018-03-19", [[0.3, 0.2], [0.1, 0.0]])
        cls._setup_test_raster("evaporation", "2018-03-19", [[110, 9.7], [9.8, 9.9]])

    @classmethod
    def _setup_test_raster(cls, var, datestr, contents):
        subdir = "forecast" if datestr >= "2018-03-18" else "historical"
        filename = os.path.join(
            cls.tempdir, subdir, "daily_{}-{}.tif".format(var, datestr)
        )
        setup_input_file(filename, np.array(contents), datestr)

    @classmethod
    def _setup_database(cls):
        cls._create_crop_type()
        cls._create_user()
        cls._create_irrigation_type()
        cls._create_agrifield()
        cls._create_custom_kc_stages()
        cls._create_applied_irrigations()

    @classmethod
    def _create_user(cls):
        cls.user = User.objects.create_user(id=55, username="bob", password="topsecret")

    @classmethod
    def _create_crop_type(cls):
        cls.crop_type = mommy.make(
            models.CropType,
            name="Grass",
            root_depth_max=0.7,
            root_depth_min=1.2,
            max_allowed_depletion=0.5,
            fek_category=4,
            kc_offseason=0.7,
            kc_plantingdate=0.7,
            planting_date=dt.date(2018, 3, 16),
        )

    @classmethod
    def _create_irrigation_type(cls):
        cls.irrigation_type = mommy.make(
            models.IrrigationType, name="Surface irrigation", efficiency=0.60
        )

    @classmethod
    def _create_agrifield(cls):
        cls.agrifield = mommy.make(
            models.Agrifield,
            id=1,
            owner=cls.user,
            name="A field",
            crop_type=cls.crop_type,
            irrigation_type=cls.irrigation_type,
            location=Point(22.0, 38.0),
            area=2000,
            custom_kc_offseason=0.3,
            custom_kc_plantingdate=0.35,
            custom_planting_date=dt.date(1970, 3, 20),
        )

    @classmethod
    def _create_custom_kc_stages(cls):
        c = models.AgrifieldCustomKcStage.objects.create
        c(agrifield=cls.agrifield, order=1, ndays=35, kc_end=0.7)
        c(agrifield=cls.agrifield, order=2, ndays=45, kc_end=1.05)

    @classmethod
    def _create_applied_irrigations(cls):
        cls.applied_irrigation_1 = mommy.make(
            models.AppliedIrrigation,
            agrifield=cls.agrifield,
            timestamp=dt.datetime(2018, 3, 15, 7, 0, tzinfo=dt.timezone.utc),
            supplied_water_volume=500,
        )
        cls.applied_irrigation_2 = mommy.make(
            models.AppliedIrrigation,
            agrifield=cls.agrifield,
            timestamp=dt.datetime(2018, 3, 19, 7, 0, tzinfo=dt.timezone.utc),
            supplied_water_volume=None,
        )

    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.mkdtemp()
        os.mkdir(os.path.join(cls.tempdir, "historical"))
        os.mkdir(os.path.join(cls.tempdir, "forecast"))
        cls._setup_rasters()
        cls._context_managers = {
            override_settings(
                AIRA_DATA_HISTORICAL=os.path.join(cls.tempdir, "historical")
            ),
            override_settings(AIRA_DATA_FORECAST=os.path.join(cls.tempdir, "forecast")),
            override_settings(AIRA_DATA_SOIL=cls.tempdir),
            freeze_time("2018-03-18 13:00:01"),
        }
        for x in cls._context_managers:
            x.__enter__()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        for x in cls._context_managers:
            x.__exit__(None, None, None)
        shutil.rmtree(cls.tempdir)
        super().tearDownClass()


class DataTestCase(SetupTestDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls._setup_database()


class ExecuteModelTestCase(DataTestCase):
    def setUp(self):
        super().setUp()
        self.results = self.agrifield.execute_model()
        self.timeseries = self.results["timeseries"]

    def test_start_date(self):
        self.assertEqual(self.timeseries.index[0], pd.Timestamp("2018-03-15 23:59"))

    def test_historical_end_date(self):
        self.assertEqual(
            self.results["historical_end_date"], pd.Timestamp("2018-03-17 23:59")
        )

    def test_forecast_start_date(self):
        self.assertEqual(
            self.results["forecast_start_date"], pd.Timestamp("2018-03-18 23:59")
        )

    def test_end_date(self):
        self.assertEqual(self.timeseries.index[-1], pd.Timestamp("2018-03-19 23:59"))

    def test_ks(self):
        self.assertAlmostEqual(self.timeseries.at["2018-03-18 23:59", "ks"], 1.0)

    def test_ifinal(self):
        self.assertAlmostEqual(self.timeseries.at["2018-03-18 23:59", "ifinal"], 0)

    def test_ifinal_m3(self):
        self.assertAlmostEqual(self.timeseries.at["2018-03-18 23:59", "ifinal_m3"], 0)

    def test_effective_precipitation(self):
        var = "effective_precipitation"
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-15 23:59"), var], 0.0
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-16 23:59"), var], 0.0
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-17 23:59"), var], 4.0
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-18 23:59"), var], 0.0
        )

    def test_dr(self):
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-18 23:59"), "dr"],
            8.8219672504910200,
            places=4,
        )

    def test_theta(self):
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-18 23:59"), "theta"],
            0.3907137186836940,
        )

    def test_actual_net_irrigation(self):
        var = "actual_net_irrigation"
        self.assertAlmostEqual(
            self.timeseries[var].at[dt.datetime(2018, 3, 15, 23, 59)], 150
        )
        self.assertAlmostEqual(
            self.timeseries.at[dt.datetime(2018, 3, 16, 23, 59), var], 0
        )
        self.assertAlmostEqual(
            self.timeseries.at[dt.datetime(2018, 3, 17, 23, 59), var], 0
        )
        self.assertAlmostEqual(
            self.timeseries.at[dt.datetime(2018, 3, 18, 23, 59), var], 0
        )
        self.assertTrue(self.timeseries.at[dt.datetime(2018, 3, 19, 23, 59), var])

    def test_ifinal_theoretical(self):
        var = "ifinal_theoretical"
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-15 23:59"), var], 0
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-16 23:59"), var], 0
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-17 23:59"), var], 0
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-18 23:59"), var], 122.08333333
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-19 23:59"), var], 125.20833333
        )


_locmemcache = "django.core.cache.backends.locmem.LocMemCache"
_in_covered_area = "aira.models.Agrifield.in_covered_area"


@override_settings(CACHES={"default": {"BACKEND": _locmemcache}})
class NeedsIrrigationTestCase(TestCase):
    def setUp(self):
        self.agrifield = mommy.make(models.Agrifield, id=1)

    def _set_needed_irrigation_amount(self, amount):
        atimeseries = pd.Series(data=[amount], index=pd.DatetimeIndex(["2020-01-15"]))
        mock_model_run = {
            "forecast_start_date": "2020-01-15",
            "timeseries": {"ifinal": atimeseries},
        }
        cache.set("model_run_1", mock_model_run)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=True)
    def test_true(self, m):
        self._set_needed_irrigation_amount(42.0)
        self.assertTrue(self.agrifield.needs_irrigation)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=True)
    def test_false(self, m):
        self._set_needed_irrigation_amount(0)
        self.assertFalse(self.agrifield.needs_irrigation)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=False)
    def test_not_in_covered_area(self, m):
        self.assertIsNone(self.agrifield.needs_irrigation)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=True)
    def test_not_in_cache(self, m):
        cache.delete("model_run_1")
        self.assertIsNone(self.agrifield.needs_irrigation)


class DefaultFieldCapacityTestCase(DataTestCase):
    def test_value(self):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertAlmostEqual(self.agrifield.default_field_capacity, 0.4)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=False)
    def test_not_in_covered_area(self, m):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertIsNone(self.agrifield.default_field_capacity)


class DefaultWiltingPointTestCase(DataTestCase):
    def test_value(self):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertAlmostEqual(self.agrifield.default_wilting_point, 0.1)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=False)
    def test_not_in_covered_area(self, m):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertIsNone(self.agrifield.default_wilting_point)


class DefaultThetaSTestCase(DataTestCase):
    def test_value(self):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertAlmostEqual(self.agrifield.default_theta_s, 0.5)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=False)
    def test_not_in_covered_area(self, m):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertIsNone(self.agrifield.default_theta_s)


@override_settings(CACHES={"default": {"BACKEND": _locmemcache}})
@patch(_in_covered_area, new_callable=PropertyMock, return_value=True)
class LastIrrigationIsOutdatedTestCase(DataTestCase):
    def setUp(self):
        super().setUp()
        self.results = self.agrifield.execute_model()
        cache.set("model_run_1", self.results)

    def test_true_if_no_irrigation(self, m):
        models.AppliedIrrigation.objects.all().delete()
        self.assertTrue(self.agrifield.last_irrigation_is_outdated)

    def test_true_if_irrigation_too_old(self, m):
        self.applied_irrigation_1.delete()
        self.applied_irrigation_2.timestamp = dt.datetime(
            2018, 3, 10, 20, 0, tzinfo=dt.timezone.utc
        )
        self.applied_irrigation_2.save()
        self.assertTrue(self.agrifield.last_irrigation_is_outdated)

    def test_false_if_irrigation_ok(self, m):
        self.assertFalse(self.agrifield.last_irrigation_is_outdated)


def mock_calculate_soil_water(**kwargs):
    timeseries = kwargs["timeseries"]
    timeseries["dr"] = 0
    timeseries["theta"] = 0
    timeseries["ks"] = 0
    timeseries["recommended_net_irrigation"] = 0
    return {"raw": 0, "taw": 0, "timeseries": timeseries}


@patch("aira.agrifield.calculate_soil_water", side_effect=mock_calculate_soil_water)
class InitialConditionsTestCase(DataTestCase):
    def tearDown(self):
        self._remove_initial_theta_rasters()

    def _check_theta_init(self, m, theta_init):
        calls = m.call_args_list
        self.assertEqual(len(calls), 2)
        for call in calls:
            call_kwargs = list(call)[1]
            self.assertAlmostEqual(call_kwargs["theta_init"], theta_init)

    def _check_starting_date(self, m, starting_date):
        calls = m.call_args_list
        self.assertEqual(len(calls), 2)
        for call in calls:
            call_kwargs = list(call)[1]
            self.assertEqual(call_kwargs["timeseries"].index[0], starting_date)

    def test_when_initial_theta_is_absent_we_start_from_field_capacity(self, m):
        self.agrifield.execute_model()
        self._check_theta_init(m, theta_init=0.4)

    def test_when_initial_theta_is_absent_we_start_from_15_march(self, m):
        self.agrifield.execute_model()
        self._check_starting_date(m, starting_date=dt.date(2018, 3, 15))

    def test_when_initial_theta_is_present_we_start_from_initial_theta(self, m):
        self._setup_initial_theta_raster("2018-03-17")
        self.agrifield.execute_model()
        self._check_theta_init(m, theta_init=0.49)

    def test_when_initial_theta_is_present_we_start_from_specified_date(self, m):
        self._setup_initial_theta_raster("2018-03-17")
        self.agrifield.execute_model()
        self._check_starting_date(m, starting_date=dt.date(2018, 3, 17))

    def test_when_initial_theta_file_has_garbage_date_we_ignore_it(self, m):
        self._setup_initial_theta_raster("garb-ag-ee")
        self.agrifield.execute_model()
        self._check_starting_date(m, starting_date=dt.date(2018, 3, 15))

    def test_when_there_are_two_initial_theta_files_we_take_the_most_recent(self, m):
        self._setup_initial_theta_raster("2018-03-16")
        self._setup_initial_theta_raster("2018-03-17")
        self.agrifield.execute_model()
        self._check_starting_date(m, starting_date=dt.date(2018, 3, 17))

    def test_when_there_are_two_initial_theta_files_we_take_the_non_garbage(self, m):
        self._setup_initial_theta_raster("2018-03-17")
        self._setup_initial_theta_raster("garb-ag-ee")
        self.agrifield.execute_model()
        self._check_starting_date(m, starting_date=dt.date(2018, 3, 17))

    def _setup_initial_theta_raster(self, date):
        self.initial_theta_filename = os.path.join(self.tempdir, f"theta-{date}.tif")
        setup_input_file(
            self.initial_theta_filename, np.array([[0.49, 0.48], [0.47, 0.46]]), None
        )

    def _remove_initial_theta_rasters(self):
        for filename in glob(os.path.join(self.tempdir, "theta-????-??-??.tif")):
            os.remove(filename)


class StartOfSeasonTestCase(TestCase):
    def setUp(self):
        self.agrifield = mommy.make(models.Agrifield)

    @freeze_time("2018-01-01 13:00:01")
    def test_jan_1(self):
        self.assertEqual(
            InitialConditions(self.agrifield).date, dt.datetime(2017, 3, 15, 0, 0)
        )

    @freeze_time("2018-03-14 13:00:01")
    def test_mar_14(self):
        self.assertEqual(
            InitialConditions(self.agrifield).date, dt.datetime(2017, 3, 15, 0, 0)
        )

    @freeze_time("2018-03-15 13:00:01")
    def test_mar_15(self):
        self.assertEqual(
            InitialConditions(self.agrifield).date, dt.datetime(2018, 3, 15, 0, 0)
        )

    @freeze_time("2018-12-31 13:00:01")
    def test_dec_31(self):
        self.assertEqual(
            InitialConditions(self.agrifield).date, dt.datetime(2018, 3, 15, 0, 0)
        )
