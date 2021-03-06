import datetime as dt
import os
import re
import shutil
import tempfile
from time import sleep
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.http import HttpRequest
from django.test import Client, TestCase, override_settings

import pandas as pd
import pytz
from bs4 import BeautifulSoup
from django_selenium_clean import PageElement, SeleniumTestCase
from model_mommy import mommy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

from aira import models, views
from aira.tests import RandomMediaRootMixin
from aira.tests.test_agrifield import DataTestCase, SetupTestDataMixin


class TestFrontPageView(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.settings_overrider = override_settings(AIRA_DATA_HISTORICAL=self.tempdir)
        self.settings_overrider.__enter__()
        open(os.path.join(self.tempdir, "daily_rain-2018-04-19.tif"), "w").close()
        self.user = User.objects.create_user(
            id=55, username="bob", password="topsecret"
        )
        self.user.save()

    def tearDown(self):
        self.settings_overrider.__exit__(None, None, None)
        shutil.rmtree(self.tempdir)

    def test_front_page_view(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_registration_link_when_anonymous_on_front_page_view(self):
        resp = self.client.get("/")
        self.assertContains(resp, "Register")

    def test_no_registration_link_when_logged_on_front_page_view(self):
        resp = self.client.login(username="bob", password="topsecret")
        self.assertTrue(resp)
        resp = self.client.get("/")
        self.assertTemplateUsed(resp, "aira/frontpage/main.html")
        self.assertNotContains(resp, "Register")

    def test_start_and_end_dates(self):
        response = self.client.get("/")
        self.assertContains(
            response,
            (
                'Time period: <span class="text-success">2018-04-19</span> : '
                '<span class="text-success">2018-04-19</span>'
            ),
            html=True,
        )


class MyFieldsViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(
            id=54, username="alice", password="topsecret"
        )

    def test_redirects(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/myfields/")
        self.assertRedirects(response, "/alice/fields/")

    def test_not_found_if_not_logged_on(self):
        response = self.client.get("/myfields/")
        self.assertEqual(response.status_code, 404)


@override_settings(
    AIRA_DEMO_USER_INITIAL_AGRIFIELDS=[
        {
            "name": "Test1",
            "coordinates": [38, 24],
            "crop_type_id": 1,
            "irrigation_type_id": 1,
            "area": 1000,
            "applied_irrigation": [
                {
                    "timestamp": "2020-12-14 15:30+0000",
                    "supplied_water_volume": 50,
                },
            ],
        }
    ]
)
class DemoViewTestCase(TestCase):
    def setUp(self):
        mommy.make(models.CropType, id=1)
        mommy.make(models.IrrigationType, id=1)
        assert not User.objects.filter(username="demo").exists()
        self.response = self.client.get("/try/")

    def test_demo_user_is_automatically_created(self):
        self.assertTrue(User.objects.filter(username="demo").exists())

    def test_redirects(self):
        self.assertRedirects(self.response, "/demo/fields/")

    def test_demo_user_is_not_created_if_it_already_exists(self):
        response = self.client.get("/try/")
        self.assertRedirects(response, "/demo/fields/")


class WrongUsernameTestMixin:
    """Adds test that wrong username results in 404.

    Many views have a URL of the form "/{username}/fields/{agrifield_id}/{remainder}".
    In these cases, the agrifield is fully specified with the {agrifield_id}; the
    {username} is not required. So we want to make sure you can't arrive at the field
    through a wrong username.

    In order to use this mixin, add it to the class parents, and specify the class
    attribute wrong_username_test_mixin_url_remainder like this:
        wrong_username_test_mixin_url_remainder =  "report"
    """

    def test_wrong_username_results_in_404(self):
        username = self.agrifield.owner.username
        remainder = self.wrong_username_test_mixin_url_remainder
        self.client.login(username=username, password="topsecret")
        assert "antonis" != username
        response = self.client.get(f"/antonis/fields/{self.agrifield.id}/{remainder}/")
        self.assertEqual(response.status_code, 404)


class SupervisedAgrifieldDetailLinksTestCase(DataTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.supervisor = User.objects.create_user(username="john", password="topsecret")
        cls.user.profile.supervisor = cls.supervisor
        cls.user.profile.save()
        models.AppliedIrrigation.objects.all().delete()

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        client = Client()
        client.login(username="john", password="topsecret")
        response = client.get("/bob/fields/")
        self.soup = BeautifulSoup(response.content.decode(), "html.parser")

    def test_applied_irrigations_button(self):
        href = self.soup.find(id="btn-applied-irrigations-1")["href"]
        self.assertEqual(href, "/bob/fields/1/appliedirrigations/")

    def test_agrifield_report_button(self):
        href = self.soup.find(id="btn-agrifield-report-1")["href"]
        self.assertEqual(href, "/bob/fields/1/report/")

    def test_irrigation_performance_button(self):
        href = self.soup.find(id="btn-irrigation-performance-1")["href"]
        self.assertEqual(href, "/bob/fields/1/performance/")

    def test_weather_history_temperature_button(self):
        href = self.soup.find(id="btn-weather-history-temperature-1")["href"]
        self.assertEqual(href, "/bob/fields/1/timeseries/temperature/")

    def test_weather_history_humidity_button(self):
        href = self.soup.find(id="btn-weather-history-humidity-1")["href"]
        self.assertEqual(href, "/bob/fields/1/timeseries/humidity/")

    def test_weather_history_rainfall_button(self):
        href = self.soup.find(id="btn-weather-history-rainfall-1")["href"]
        self.assertEqual(href, "/bob/fields/1/timeseries/rain/")

    def test_weather_history_solar_radiation_button(self):
        href = self.soup.find(id="btn-weather-history-solar-radiation-1")["href"]
        self.assertEqual(href, "/bob/fields/1/timeseries/solar_radiation/")

    def test_weather_history_wind_speed_button(self):
        href = self.soup.find(id="btn-weather-history-wind-speed-1")["href"]
        self.assertEqual(href, "/bob/fields/1/timeseries/wind_speed/")

    def test_weather_history_evaporation_button(self):
        href = self.soup.find(id="btn-weather-history-evaporation-1")["href"]
        self.assertEqual(href, "/bob/fields/1/timeseries/evaporation/")

    def test_update_agrifield_button(self):
        href = self.soup.find(id="btn-update-agrifield-1")["href"]
        self.assertEqual(href, "/bob/fields/1/edit/")

    def test_applied_irrigations_link_in_warning(self):
        href = self.soup.find(id="link-applied-irrigations-warning-1")["href"]
        self.assertEqual(href, "/bob/fields/1/appliedirrigations/")


class UpdateAgrifieldViewTestCase(WrongUsernameTestMixin, DataTestCase):
    wrong_username_test_mixin_url_remainder = "edit"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls._create_crop_type_kc_stages()
        cls._make_request()

    @classmethod
    def _create_crop_type_kc_stages(cls):
        c = models.CropTypeKcStage.objects.create
        c(crop_type=cls.crop_type, order=1, ndays=32, kc_end=0.6)
        c(crop_type=cls.crop_type, order=2, ndays=42, kc_end=0.95)

    @classmethod
    def _make_request(cls):
        cls.client = Client()
        cls.client.login(username="bob", password="topsecret")
        cls.response = cls.client.get(f"/bob/fields/{cls.agrifield.id}/edit/")

    def test_response_contains_agrifield_name(self):
        self.assertContains(self.response, "A field")

    def test_default_irrigation_efficiency(self):
        self.assertContains(
            self.response,
            '<span id="default-irrigation-efficiency">0.6</span>',
            html=True,
        )

    def test_default_max_allowed_depletion(self):
        self.assertContains(
            self.response,
            '<span id="default-max_allowed_depletion">0.50</span>',
            html=True,
        )

    def test_default_root_depth_max(self):
        self.assertContains(
            self.response, '<span id="default-root_depth_max">0.7</span>', html=True
        )

    def test_default_root_depth_min(self):
        self.assertContains(
            self.response, '<span id="default-root_depth_min">1.2</span>', html=True
        )

    def test_default_irrigation_optimizer(self):
        self.assertContains(
            self.response,
            '<span id="default-irrigation-optimizer">0.5</span>',
            html=True,
        )

    def test_default_field_capacity(self):
        self.assertContains(
            self.response, '<span id="default-field-capacity">0.40</span>', html=True
        )

    def test_default_wilting_point(self):
        self.assertContains(
            self.response, '<span id="default-wilting-point">0.10</span>', html=True
        )

    def test_default_theta_s(self):
        self.assertContains(
            self.response, '<span id="default-theta_s">0.50</span>', html=True
        )

    def test_kc_stages(self):
        self.assertContains(self.response, "35\t0.7\n45\t1.05")

    def test_kc_stages_placeholder(self):
        soup = BeautifulSoup(self.response.content, "html.parser")
        kc_stages_element = soup.find("textarea", id="id_kc_stages")
        self.assertIsNone(kc_stages_element.get("placeholder"))

    def test_default_kc_stages(self):
        self.assertContains(
            self.response,
            '<div id="default-kc_stages"><p>32\t0.6<br>42\t0.95</p></div>',
            html=True,
        )

    def test_kc_plantingdate(self):
        soup = BeautifulSoup(self.response.content, "html.parser")
        kc_plantingdate_element = soup.find("input", id="id_custom_kc_plantingdate")
        self.assertEqual(kc_plantingdate_element.get("value"), "0.35")

    def test_kc_plantingdate_placeholder(self):
        soup = BeautifulSoup(self.response.content, "html.parser")
        kc_plantingdate_element = soup.find("input", id="id_custom_kc_plantingdate")
        self.assertEqual(kc_plantingdate_element.get("placeholder"), "0.3 - 1.25")

    def test_default_kc_plantingdate(self):
        self.assertContains(
            self.response, '<span id="default-kc_plantingdate">0.7</span>', html=True
        )

    def test_kc_offseason(self):
        soup = BeautifulSoup(self.response.content, "html.parser")
        kc_offseason_element = soup.find("input", id="id_custom_kc_offseason")
        self.assertEqual(kc_offseason_element.get("value"), "0.3")

    def test_kc_offseason_placeholder(self):
        soup = BeautifulSoup(self.response.content, "html.parser")
        kc_offseason_element = soup.find("input", id="id_custom_kc_offseason")
        self.assertEqual(kc_offseason_element.get("placeholder"), "0.3 - 1.25")

    def test_default_kc_offseason(self):
        self.assertContains(
            self.response, '<span id="default-kc_offseason">0.7</span>', html=True
        )

    def test_kc_planting_date(self):
        soup = BeautifulSoup(self.response.content, "html.parser")
        planting_date_element = soup.find("input", id="id_custom_planting_date")
        self.assertEqual(planting_date_element.get("value"), "20/03")

    def test_planting_date_placeholder(self):
        soup = BeautifulSoup(self.response.content, "html.parser")
        planting_date_element = soup.find("input", id="id_custom_planting_date")
        self.assertEqual(planting_date_element.get("placeholder"), "day/month")

    def test_default_planting_date(self):
        self.assertContains(
            self.response, '<span id="default-planting_date">16 Mar</span>', html=True
        )


class DeleteAgrifieldViewTestCase(WrongUsernameTestMixin, DataTestCase):
    wrong_username_test_mixin_url_remainder = "delete"


class UpdateAgrifieldViewWithEmptyDefaultKcStagesTestCase(DataTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls._make_request()

    @classmethod
    def _make_request(cls):
        cls.client = Client()
        cls.client.login(username="bob", password="topsecret")
        cls.response = cls.client.get(f"/bob/fields/{cls.agrifield.id}/edit/")

    def test_default_kc_stages(self):
        self.assertContains(
            self.response, '<span id="default-kc_stages">Unspecified</span>', html=True
        )


class CreateAgrifieldViewTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            id=54, username="alice", password="topsecret"
        )
        self.client.login(username="alice", password="topsecret")
        self.response = self.client.get("/alice/fields/create/")

    def test_status_code(self):
        self.assertEqual(self.response.status_code, 200)


class AgrifieldTimeseriesViewTestCase(WrongUsernameTestMixin, TestCase):
    wrong_username_test_mixin_url_remainder = "timeseries/temperature"

    def setUp(self):
        self._create_stuff()
        self._login()
        self._get_response()

    def _create_stuff(self):
        self._create_tempdir()
        self._override_settings()
        self._create_user()
        self._create_agrifield()
        self._create_dummy_result_file()

    def _create_tempdir(self):
        self.tempdir = tempfile.mkdtemp()

    def _override_settings(self):
        self.settings_overrider = override_settings(
            AIRA_TIMESERIES_CACHE_DIR=self.tempdir
        )
        self.settings_overrider.__enter__()

    def _create_dummy_result_file(self):
        self.dummy_result_pathname = os.path.join(
            settings.AIRA_TIMESERIES_CACHE_DIR,
            "agrifield{}-temperature.hts".format(self.agrifield.id),
        )
        with open(self.dummy_result_pathname, "w") as f:
            f.write("These are the dummy result file contents")

    def _create_user(self):
        self.alice = User.objects.create_user(
            id=54, username="alice", password="topsecret"
        )

    def _create_agrifield(self):
        self.agrifield = mommy.make(
            models.Agrifield, name="hello", location=Point(23, 38), owner=self.alice
        )

    def _login(self):
        self.client.login(username="alice", password="topsecret")

    def _get_response(self):
        patcher = patch(
            "aira.models.PointTimeseries",
            **{"return_value.get_cached.return_value": self.dummy_result_pathname},
        )
        with patcher as m:
            self.mock_point_timeseries = m
            self.response = self.client.get(
                f"/alice/fields/{self.agrifield.id}/timeseries/temperature/"
            )

    def tearDown(self):
        self.settings_overrider.__exit__(None, None, None)
        shutil.rmtree(self.tempdir)

    def test_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_response_contents(self):
        content = b""
        for chunk in self.response.streaming_content:
            content += chunk
        self.assertEqual(content, b"These are the dummy result file contents")

    def test_called_point_timeseries(self):
        self.mock_point_timeseries.assert_called_once_with(
            point=self.agrifield.location,
            prefix=os.path.join(settings.AIRA_DATA_HISTORICAL, "daily_temperature"),
            default_time=dt.time(23, 59),
        )

    def test_called_get_cached(self):
        self.mock_point_timeseries.return_value.get_cached.assert_called_once_with(
            self.dummy_result_pathname, version=2
        )


class DownloadSoilAnalysisViewTestCase(
    WrongUsernameTestMixin, TestCase, RandomMediaRootMixin
):
    wrong_username_test_mixin_url_remainder = "soil_analysis"

    def setUp(self):
        self.override_media_root()
        self.alice = User.objects.create_user(
            id=54, username="alice", password="topsecret"
        )
        self.agrifield = mommy.make(models.Agrifield, id=1, owner=self.alice)
        self.agrifield.soil_analysis.save("somefile", ContentFile("hello world"))
        self.client.login(username="alice", password="topsecret")
        self.response = self.client.get("/alice/fields/1/soil_analysis/")

    def tearDown(self):
        self.end_media_root_override()

    def test_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_content(self):
        content = b""
        for x in self.response.streaming_content:
            content += x
        self.assertEqual(content, b"hello world")


class AgrifieldReportViewTestCase(WrongUsernameTestMixin, DataTestCase):
    wrong_username_test_mixin_url_remainder = "report"

    def _make_request(self):
        self.client.login(username="bob", password="topsecret")
        self.response = self.client.get(f"/bob/fields/{self.agrifield.id}/report/")

    def _update_agrifield(self, **kwargs):
        for key in kwargs:
            if not hasattr(self.agrifield, key):
                raise KeyError("Agrifield doesn't have key {}".format(key))
            setattr(self.agrifield, key, kwargs[key])
        self.agrifield.save()

    def test_response_contains_default_root_depth(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Estimated root depth (max):</b> 0.95 m")

    def test_response_contains_custom_root_depth(self):
        self._update_agrifield(
            use_custom_parameters=True,
            custom_root_depth_min=0.1,
            custom_root_depth_max=0.30000001,
        )
        self._make_request()
        self.assertContains(self.response, "<b>Estimated root depth (max):</b> 0.20 m")

    def test_response_contains_default_field_capacity(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Field capacity:</b> 40.0%")

    def test_response_contains_custom_field_capacity(self):
        self._update_agrifield(use_custom_parameters=True, custom_field_capacity=0.321)
        self._make_request()
        self.assertContains(self.response, "<b>Field capacity:</b> 32.1%")

    def test_response_contains_default_theta_s(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(
            self.response, "<b>Soil moisture at saturation (??<sub>s</sub>):</b> 50.0%"
        )

    def test_response_contains_custom_theta_s(self):
        self._update_agrifield(use_custom_parameters=True, custom_thetaS=0.424)
        self._make_request()
        self.assertContains(
            self.response, "<b>Soil moisture at saturation (??<sub>s</sub>):</b> 42.4%"
        )

    def test_response_contains_default_pwp(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Permanent wilting point:</b> 10.0%")

    def test_response_contains_custom_pwp(self):
        self._update_agrifield(use_custom_parameters=True, custom_wilting_point=0.117)
        self._make_request()
        self.assertContains(self.response, "<b>Permanent wilting point:</b> 11.7%")

    def test_response_contains_default_irrigation_efficiency(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Irrigation efficiency:</b> 0.6")

    def test_response_contains_custom_irrigation_efficiency(self):
        self._update_agrifield(use_custom_parameters=True, custom_efficiency=0.88)
        self._make_request()
        self.assertContains(self.response, "<b>Irrigation efficiency:</b> 0.88")

    def test_response_contains_default_irrigation_optimizer(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Irrigation optimizer:</b> 0.5")

    def test_response_contains_custom_irrigation_optimizer(self):
        self._update_agrifield(
            use_custom_parameters=True, custom_irrigation_optimizer=0.55
        )
        self._make_request()
        self.assertContains(self.response, "<b>Irrigation optimizer:</b> 0.55")

    def test_response_contains_no_last_irrigation(self):
        self.agrifield.appliedirrigation_set.all().delete()
        self._make_request()
        self.assertContains(
            self.response, "<b>Last recorded irrigation:</b> Unspecified"
        )

    def test_response_contains_last_irrigation_with_specified_applied_water(self):
        tz = pytz.timezone(settings.TIME_ZONE)
        mommy.make(
            models.AppliedIrrigation,
            agrifield=self.agrifield,
            timestamp=tz.localize(dt.datetime(2019, 9, 11, 17, 23)),
            supplied_water_volume=100.5,
        )
        self._make_request()
        self.assertContains(
            self.response, "<b>Last recorded irrigation:</b> 11/09/2019 17:00"
        )
        self.assertContains(self.response, "<b>Applied water (m??):</b> 100.5")

    def test_response_contains_last_irrigation_with_unspecified_applied_water(self):
        tz = pytz.timezone(settings.TIME_ZONE)
        mommy.make(
            models.AppliedIrrigation,
            agrifield=self.agrifield,
            timestamp=tz.localize(dt.datetime(2019, 9, 11, 17, 23)),
            supplied_water_volume=None,
        )
        self._update_agrifield(area=653.7)
        self._make_request()
        self.assertContains(
            self.response, "<b>Last recorded irrigation:</b> 11/09/2019 17:00 <br>"
        )
        self.assertContains(
            self.response,
            "<b>Applied water (m??):</b> 93.2 "
            "(Irrigation water is estimated using system's "
            "default parameters.)",
        )


class RemoveSuperviseeTestCase(DataTestCase):
    def setUp(self):
        super().setUp()
        # Note: we give specific ids below to the users, to ensure the general case,
        # that profile ids are different from user ids.
        self.charlie = User.objects.create_user(
            id=56, username="charlie", password="topsecret"
        )
        self.charlie.profile.first_name = "Charlie"
        self.charlie.profile.last_name = "Clark"
        self.charlie.profile.supervisor = self.user
        self.charlie.profile.save()
        self.david = User.objects.create_user(
            id=57, username="david", password="topsecret"
        )

    def test_supervisee_list_contains_charlie(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/bob/supervisees/")
        self.assertContains(response, 'href="/charlie/fields/"')

    def test_supervisee_remove_button_input_field(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/bob/supervisees/")
        soup = BeautifulSoup(response.content.decode(), "html.parser")
        input_field = soup.find("input", attrs={"name": "supervisee_id"})
        self.assertEqual(input_field["value"], "56")

    def test_remove_charlie_from_supervisees(self):
        assert User.objects.get(username="charlie").profile.supervisor is not None
        self.client.login(username="bob", password="topsecret")
        response = self.client.post(
            "/bob/supervisees/remove/", data={"supervisee_id": "56"}
        )
        self.assertRedirects(response, "/bob/supervisees/")
        self.assertIsNone(User.objects.get(username="charlie").profile.supervisor)

    def test_attempting_to_remove_charlie_when_not_logged_in_returns_404(self):
        response = self.client.post(
            "/bob/supervisees/remove/", data={"supervisee_id": self.charlie.id}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(User.objects.get(username="charlie").profile.supervisor)

    def test_attempting_to_remove_charlie_when_logged_in_as_david_returns_404(self):
        self.client.login(username="david", password="topsecret")
        response = self.client.post(
            "/bob/supervisees/remove/", data={"supervisee_id": self.charlie.id}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(User.objects.get(username="charlie").profile.supervisor)

    def test_attempting_to_remove_when_already_removed_returns_404(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.post(
            "/bob/supervisees/remove/", data={"supervisee_id": self.david.id}
        )
        self.assertEqual(response.status_code, 404)

    def test_attempting_to_remove_garbage_id_returns_404(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.post(
            "/bob/supervisees/remove/", data={"supervisee_id": "garbage"}
        )
        self.assertEqual(response.status_code, 404)

    def test_posting_without_parameters_returns_404(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.post("/bob/supervisees/remove/")
        self.assertEqual(response.status_code, 404)

    def test_post_request_returns_404_if_wrong_user_in_url(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.post(
            "/david/supervisees/remove/", {"supervisee_id": self.charlie.id}
        )
        self.assertEqual(response.status_code, 404)

    def test_get_request_returns_404(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/bob/supervisees/remove/")
        self.assertEqual(response.status_code, 404)


class SuperviseesViewTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        client = Client()
        client.login(username="alice", password="topsecret")
        cls.response = client.get("/alice/supervisees/")

    @classmethod
    def setUpTestData(cls):
        cls.alice = cls._create_user(
            56, "alice", "Alice", "Aniston", "alice@aniston.com"
        )
        cls.bob = cls._create_user(
            57, "bob", "Bob", "Brown", "bob@brown.com", supervisor=cls.alice
        )
        cls.david = cls._create_user(
            58, "david", "David", "Davidson", "dave@davidson.com", supervisor=cls.alice
        )
        cls.charlie = cls._create_user(
            59, "charlie", "Charlie", "Clark", "ch@clark.com", supervisor=cls.alice
        )

    @classmethod
    def _create_user(cls, id, username, first_name, last_name, email, supervisor=None):
        user = User.objects.create_user(
            id=id, username=username, password="topsecret", email=email
        )
        user.profile.first_name = first_name
        user.profile.last_name = last_name
        if supervisor:
            user.profile.supervisor = supervisor
        user.profile.save()
        return user

    def test_get_queryset(self):
        view = views.SuperviseesView()
        view.request = HttpRequest()
        view.request.user = self.alice
        self.assertEqual(
            list(view.get_queryset()),
            [self.bob.profile, self.charlie.profile, self.david.profile],
        )

    def test_response_contains_email(self):
        self.assertContains(self.response, "bob@brown.com")

    def test_response_contains_link_to_supervisee_fields(self):
        self.assertContains(self.response, 'href="/bob/fields/"')

    def test_response_contains_link_to_remove_supervisee(self):
        self.assertContains(self.response, 'action="/alice/supervisees/remove/"')


_locmemcache = "django.core.cache.backends.locmem.LocMemCache"


@override_settings(CACHES={"default": {"BACKEND": _locmemcache}})
class LastIrrigationOutsidePeriodWarningTestCase(DataTestCase):
    message = "You haven't registered any irrigation"

    def setUp(self):
        super().setUp()
        self._create_applied_irrigation()
        self._login()

    def _create_applied_irrigation(self):
        tz = pytz.timezone(settings.TIME_ZONE)
        mommy.make(
            models.AppliedIrrigation,
            agrifield=self.agrifield,
            timestamp=tz.localize(dt.datetime(2019, 10, 25, 6, 30)),
            supplied_water_volume=58,
        )

    def _login(self):
        self.client.login(username="bob", password="topsecret")

    def _setup_results_between(self, start_date, end_date):
        df = pd.DataFrame(
            data=[41, 42],
            index=pd.DatetimeIndex([start_date, end_date]),
            columns=["ifinal"],
        )
        cache.set(
            "model_run_1",
            {"timeseries": df, "forecast_start_date": end_date - dt.timedelta(1)},
        )

    def test_no_warning_if_no_calculations(self):
        cache.set("model_run_1", None)
        response = self.client.get("/bob/fields/")
        self.assertNotContains(response, self.message)

    def test_warning_if_outside_period(self):
        self._setup_results_between(dt.datetime(2019, 3, 15), dt.datetime(2019, 9, 15))
        response = self.client.get("/bob/fields/")
        self.assertContains(response, self.message)

    def test_no_warning_if_inside_period(self):
        self._setup_results_between(dt.datetime(2019, 3, 15), dt.datetime(2019, 12, 15))
        response = self.client.get("/bob/fields/")
        self.assertNotContains(response, self.message)


@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
class DailyMonthlyToggleButtonTestCase(SeleniumTestCase):
    toggle_button = PageElement(By.ID, "timestep-toggle")

    def test_daily_monthly_toggle(self):
        self.selenium.get(self.live_server_url)
        self.toggle_button.wait_until_exists()
        self.assertEqual(self.toggle_button.text, "Switch to monthly")

        self.toggle_button.click()
        sleep(0.1)
        self.assertEqual(self.toggle_button.text, "Switch to daily")


@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
class DateChangingTestCase(SeleniumTestCase):
    previous_date_button = PageElement(By.ID, "previous-date")
    next_date_button = PageElement(By.ID, "next-date")
    current_date_element = PageElement(By.ID, "current-date")
    date_input_element = PageElement(By.ID, "date-input")
    calendar_icon_element = PageElement(By.ID, "calendar-icon")
    datetimepicker_2 = PageElement(By.XPATH, '//td[@class="day"][text()="2"]')

    def _check_button_values(self, previous, current, next):
        self.assertEqual(self.current_date_element.text, current)
        self._check_button(self.previous_date_button, previous)
        self._check_button(self.next_date_button, next)

    def _check_button(self, button, expected_value):
        val = button.text
        if not expected_value:
            self.assertEqual(val, "")
        else:
            self.assertTrue(
                val.startswith(expected_value) or val.endswith(expected_value)
            )

    def test_date_changing_buttons(self):
        self.selenium.get(self.live_server_url)
        self.previous_date_button.wait_until_exists()
        self.current_date_element.wait_until_exists()
        self.next_date_button.wait_until_exists()
        self._check_button_values("2019-01-02", "2019-01-03", None)

        self.previous_date_button.click()
        sleep(0.1)
        self._check_button_values("2019-01-01", "2019-01-02", "2019-01-03")

        self.previous_date_button.click()
        sleep(0.1)
        self._check_button_values(None, "2019-01-01", "2019-01-02")

        self.next_date_button.click()
        sleep(0.1)
        self._check_button_values("2019-01-01", "2019-01-02", "2019-01-03")

        self.next_date_button.click()
        sleep(0.1)
        self._check_button_values("2019-01-02", "2019-01-03", None)

    def test_specify_date(self):
        self.selenium.get(self.live_server_url)
        self.previous_date_button.wait_until_exists()
        self.current_date_element.wait_until_exists()
        self.next_date_button.wait_until_exists()
        self._check_button_values("2019-01-02", "2019-01-03", None)

        self.calendar_icon_element.wait_until_exists()
        self.calendar_icon_element.click()
        self.datetimepicker_2.wait_until_exists()
        self.datetimepicker_2.click()
        sleep(0.1)
        self._check_button_values("2019-01-01", "2019-01-02", "2019-01-03")


class ResetPasswordTestCase(TestCase):
    def setUp(self):
        User.objects.create_user("alice", "alice@wonderland.com", password="topsecret")

    def test_asking_for_password_reset_works_ok(self):
        r = self.client.post(
            "/accounts/password/reset/", data={"email": "alice@wonderland.com"}
        )
        self.assertEqual(r.status_code, 302)


class IrrigationPerformanceViewTestCase(WrongUsernameTestMixin, DataTestCase):
    wrong_username_test_mixin_url_remainder = "performance"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.results = cls.agrifield.execute_model()
        cls.client = Client()
        cls.client.login(username="bob", password="topsecret")
        cls.response = cls.client.get(f"/bob/fields/{cls.agrifield.id}/performance/")
        assert cls.response.status_code == 200
        cls.series = cls._extract_series_from_javascript(cls.response.content.decode())

    _series_regexp = r"""
        \sseries:\s* # "series:" preceded by space and followed by optional whitespace.
        (?P<series>
            \[\s*              # Bracket that starts the list.
            ({[^}]*}\s*,?\s*)* # "{" plus non-"}" characters plus "}" plus optional
                               # comma, all that repeated as many times as needed.
            \s*\]              # Bracket that ends the list.
        )
    """

    @classmethod
    def _extract_series_from_javascript(cls, page_content):
        m = re.search(cls._series_regexp, page_content, re.VERBOSE)
        series = eval(m.group("series"))
        result = {x["name"]: x["data"] for x in series}
        return result

    def test_applied_water_when_irrigation_specified(self):
        self.assertAlmostEqual(self.series["Applied irrigation water amount"][0], 250)

    def test_applied_water_when_irrigation_determined_automatically(self):
        self.assertAlmostEqual(
            self.series["Applied irrigation water amount"][4], 125.20833333
        )

    def test_total_applied_water(self):
        m = re.search(
            r"Total applied irrigation water amount[^:]*:\s*(\d+)\s*mm",
            self.response.content.decode(),
            re.MULTILINE,
        )
        total_applied_water = int(m.group(1))
        self.assertEqual(total_applied_water, 375)


class IrrigationPerformanceCsvTestCase(WrongUsernameTestMixin, DataTestCase):
    wrong_username_test_mixin_url_remainder = "performance/download"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.results = cls.agrifield.execute_model()

    def _get_response(self):
        self.client.login(username="bob", password="topsecret")
        self.response = self.client.get(
            f"/bob/fields/{self.agrifield.id}/performance/download/"
        )
        assert self.response.status_code == 200

    def test_applied_water_when_irrigation_specified(self):
        self._get_response()
        m = re.search(
            r"2018-03-15 23:59:00,[.\d]*,([.\d]*),",
            self.response.content.decode(),
            re.MULTILINE,
        )
        value = float(m.group(1))
        self.assertAlmostEqual(value, 250.0)

    def test_applied_water_when_irrigation_determined_automatically(self):
        self._get_response()
        m = re.search(
            r"2018-03-19 23:59:00,[.\d]*,([.\d]*),",
            self.response.content.decode(),
            re.MULTILINE,
        )
        value = float(m.group(1))
        self.assertAlmostEqual(value, 125.20833333)


class AppliedIrrigationsViewTestCase(WrongUsernameTestMixin, TestCase):
    wrong_username_test_mixin_url_remainder = "appliedirrigations"

    def setUp(self):
        owner = User.objects.create_user(username="bob", password="topsecret")
        self.client.login(username="bob", password="topsecret")
        self.agrifield = mommy.make(models.Agrifield, owner=owner)

    @patch("aira.models.Agrifield.get_applied_irrigation_defaults")
    def test_applied_irrigation_defaults(self, mock):
        mock.return_value = {
            "supplied_water_volume": 1337,
            "irrigation_type": "HELLO_WORLD",
        }
        response = self.client.get(
            f"/bob/fields/{self.agrifield.id}/appliedirrigations/"
        )
        initials = response.context["add_irrigation_form"].initial
        self.assertEqual(initials["supplied_water_volume"], 1337)
        self.assertEqual(initials["irrigation_type"], "HELLO_WORLD")

    def test_submit_form(self):
        response = self.client.post(
            f"/bob/fields/{self.agrifield.id}/appliedirrigations/",
            data={
                "agrifield": self.agrifield.id,
                "irrigation_type": "VOLUME_OF_WATER",
                "timestamp": "2020-11-10 13:00",
                "supplied_water_volume": "50.0",
            },
        )
        self.assertEqual(response.status_code, 302)


class AppliedIrrigationWrongAgrifieldTestMixin:
    """Adds test that wrong agrifield results in 404.

    Some applied irrigation views have a URL of the form
    "/{username}/fields/{agrifield_id}/appliedirrigations/{applied_irrigation_id}
    /remainder".  In these cases, the applied irrigation is fully specified with the
    {applied_irrigation_id}; the {agrifield_id} is not required. So we want to make sure
    you can't arrive at the applied irrigation through a wrong agrifield.

    In order to use this mixin, add it to the class parents, and specify the class
    attribute applied_irrigation_wrong_agrifield_test_mixin_url_remainder like this:
        applied_irrigation_wrong_agrifield_test_mixin_url_remainder = "delete"

    See also WrongUsernameTestMixin.
    """

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create_user(username="bob", password="topsecret")
        cls.agrifield = mommy.make(models.Agrifield, owner=owner)
        cls.agrifield2 = mommy.make(models.Agrifield, owner=owner)
        cls.applied_irrigation = mommy.make(
            models.AppliedIrrigation, agrifield=cls.agrifield, id=101
        )

    def test_wrong_agrifield_results_in_404(self):
        remainder = self.applied_irrigation_wrong_agrifield_test_mixin_url_remainder
        self.client.login(username=self.agrifield.owner.username, password="topsecret")
        url = (
            f"/{self.agrifield.owner.username}/fields/{self.agrifield2.id}/"
            f"appliedirrigations/{self.applied_irrigation.id}/{remainder}/"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class AppliedIrrigationEditViewTestCase(
    WrongUsernameTestMixin, AppliedIrrigationWrongAgrifieldTestMixin, TestCase
):
    wrong_username_test_mixin_url_remainder = "appliedirrigations/101/edit"
    applied_irrigation_wrong_agrifield_test_mixin_url_remainder = "edit"


class AppliedIrrigationDeleteViewTestCase(
    WrongUsernameTestMixin, AppliedIrrigationWrongAgrifieldTestMixin, TestCase
):
    wrong_username_test_mixin_url_remainder = "appliedirrigations/101/delete"
    applied_irrigation_wrong_agrifield_test_mixin_url_remainder = "delete"

    def test_redirection(self):
        self.client.login(username="bob", password="topsecret")
        field_id = self.agrifield.id
        response = self.client.post(
            f"/bob/fields/{field_id}/appliedirrigations/101/delete/"
        )
        self.assertRedirects(response, f"/bob/fields/{field_id}/appliedirrigations/")


class SupervisedAgrifieldAppliedIrrigationLinksTestCase(DataTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.supervisor = User.objects.create_user(username="john", password="topsecret")
        cls.user.profile.supervisor = cls.supervisor
        cls.user.profile.save()
        cls.applied_irrigation = mommy.make(
            models.AppliedIrrigation, agrifield=cls.agrifield, id=101
        )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        client = Client()
        client.login(username="john", password="topsecret")
        response = client.get("/bob/fields/1/appliedirrigations/")
        cls.soup = BeautifulSoup(response.content.decode(), "html.parser")

    def test_update_applied_irrigation_link(self):
        href = self.soup.find(id="link-update-applied-irrigation-101")["href"]
        self.assertEqual(href, "/bob/fields/1/appliedirrigations/101/edit/")

    def test_delete_applied_irrigation_link(self):
        href = self.soup.find(id="link-delete-applied-irrigation-101")["href"]
        self.assertEqual(href, "/bob/fields/1/appliedirrigations/101/delete/")


class SupervisedAgrifieldAppliedIrrigationEditLinksTestCase(DataTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.supervisor = User.objects.create_user(username="john", password="topsecret")
        cls.user.profile.supervisor = cls.supervisor
        cls.user.profile.save()
        cls.applied_irrigation = mommy.make(
            models.AppliedIrrigation, agrifield=cls.agrifield, id=101
        )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        client = Client()
        client.login(username="john", password="topsecret")
        response = client.get("/bob/fields/1/appliedirrigations/101/edit/")
        cls.soup = BeautifulSoup(response.content.decode(), "html.parser")

    def test_back_button(self):
        href = self.soup.find(id="btn-back")["href"]
        self.assertEqual(href, "/bob/fields/1/appliedirrigations/")


@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
@override_settings(AIRA_MAP_DEFAULT_CENTER=(22.01, 37.99))
class MapPopupTestCase(SeleniumTestCase, DataTestCase):
    map_element = PageElement(By.ID, "map")
    popup_element = PageElement(By.CSS_SELECTOR, "div.leaflet-popup")

    def setUp(self):
        self.saved_template_name = views.FrontPageView.template_name
        self.mock_template_name = "aira/frontpage/tmpmain.html"
        views.FrontPageView.template_name = self.mock_template_name
        with open("aira/templates/" + self.mock_template_name, "w") as f:
            f.write(
                r"""\
                {% extends "aira/frontpage/main-default.html" %}
                {% block extrajs %}
                  {{block.super}}
                  <script src="https://unpkg.com/xhr-mock/dist/xhr-mock.js"></script>
                  <script>
                    XHRMock.setup()
                    XHRMock.get(/\.*/, {
                        body: 'Hello, world!'
                    });
                  </script>
                {% endblock %}
                """
            )

    def tearDown(self):
        os.remove("aira/templates/" + self.mock_template_name)
        views.FrontPageView.template_name = self.saved_template_name

    def test_popup(self):
        # Visit front page and ensure there's no popup
        self.selenium.get(self.live_server_url)
        self.map_element.wait_until_exists()
        self.assertFalse(self.popup_element.exists())

        # Click in the map
        ActionChains(self.selenium).move_to_element(
            self.selenium.find_element(By.ID, "map")
        ).move_by_offset(20, 20).click().perform()
        sleep(0.1)

        # The popup should now appear
        self.assertTrue(self.popup_element.exists())


class SeleniumDataTestCase(SetupTestDataMixin, SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self._setup_database()


@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
class AgrifieldsMapTestCase(SeleniumDataTestCase):
    map_element = PageElement(By.ID, "map")
    map_marker = PageElement(By.CSS_SELECTOR, "img.leaflet-marker-icon")

    def test_agrifields_map(self):
        # Visit user's agrifields list page
        r = self.selenium.login(username="bob", password="topsecret")
        self.assertTrue(r)
        self.selenium.get(self.live_server_url + "/bob/fields/")
        self.map_element.wait_until_exists()

        # Check that there is a marker on the map (it marks the agrifield)
        self.assertTrue(self.map_marker.exists())


@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
class AgrifieldEditMapTestCase(SeleniumDataTestCase):
    map_element = PageElement(By.ID, "map")
    map_marker = PageElement(By.CSS_SELECTOR, "img.leaflet-marker-icon")
    longitude_element = PageElement(By.ID, "id_location_0")
    latitude_element = PageElement(By.ID, "id_location_1")

    def test_agrifields_map(self):
        # Visit user's edit agrifield list page
        r = self.selenium.login(username="bob", password="topsecret")
        self.assertTrue(r)
        self.selenium.get(self.live_server_url + "/bob/fields/1/edit/")
        self.map_element.wait_until_exists()

        # Check that there is a marker on the map (it marks the agrifield)
        self.assertTrue(self.map_marker.exists())

        # Save the latitude and longitude values
        original_latitude = self.latitude_element.get_attribute("value")
        original_longitude = self.longitude_element.get_attribute("value")

        # Click near the left edge of the map
        x_offset = self.map_element.size["width"] / 2
        y_offset = 20
        ActionChains(self.selenium).move_to_element(
            self.selenium.find_element(By.ID, "map")
        ).move_by_offset(x_offset, y_offset).click().perform()
        sleep(0.1)

        # The co-ordinates should have changed
        new_latitude = self.latitude_element.get_attribute("value")
        new_longitude = self.longitude_element.get_attribute("value")
        self.assertNotEqual(new_latitude, original_latitude)
        self.assertNotEqual(new_longitude, original_longitude)

    def test_agrifields_map_in_new_agrifields(self):
        # Visit user's add agrifield list page
        r = self.selenium.login(username="bob", password="topsecret")
        self.assertTrue(r)
        self.selenium.get(self.live_server_url + "/bob/fields/create/")
        self.map_element.wait_until_exists()

        # Check that latitude and longitude values are empty
        self.assertEqual(self.latitude_element.get_attribute("value"), "")
        self.assertEqual(self.longitude_element.get_attribute("value"), "")

        # Click near the left edge of the map
        x_offset = self.map_element.size["width"] / 2
        y_offset = 20
        ActionChains(self.selenium).move_to_element(
            self.selenium.find_element(By.ID, "map")
        ).move_by_offset(x_offset, y_offset).click().perform()
        sleep(0.1)

        # The co-ordinates should have been set
        self.assertNotEqual(self.latitude_element.get_attribute("value"), "")
        self.assertNotEqual(self.longitude_element.get_attribute("value"), "")


@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
class AddIrrigationTestCase(SeleniumDataTestCase):
    water_volume_radio = PageElement(By.ID, "id_irrigation_type_0")
    irrigation_duration_radio = PageElement(By.ID, "id_irrigation_type_1")
    flowmeter_radio = PageElement(By.ID, "id_irrigation_type_2")
    timestamp_input = PageElement(By.ID, "id_timestamp")
    supplied_water_volume_input = PageElement(By.ID, "id_supplied_water_volume")
    supplied_duration_input = PageElement(By.ID, "id_supplied_duration")
    supplied_flow_rate_input = PageElement(By.ID, "id_supplied_flow_rate")
    flowmeter_reading_start_input = PageElement(By.ID, "id_flowmeter_reading_start")
    flowmeter_reading_end_input = PageElement(By.ID, "id_flowmeter_reading_end")
    flowmeter_water_percentage_input = PageElement(
        By.ID, "id_flowmeter_water_percentage"
    )

    def assert_visibility(self, wv, d, f, frs, fre, fwp):
        self._check_against(self.supplied_water_volume_input, wv)
        self._check_against(self.supplied_duration_input, d)
        self._check_against(self.supplied_flow_rate_input, f)
        self._check_against(self.flowmeter_reading_start_input, frs)
        self._check_against(self.flowmeter_reading_end_input, fre)
        self._check_against(self.flowmeter_water_percentage_input, fwp)

    def _check_against(self, element, expected_visibility):
        if expected_visibility:
            self.assertTrue(element.is_displayed())
        else:
            self.assertFalse(element.is_displayed())

    def test_add_irrigation(self):
        # Visit user's add irrigation page
        r = self.selenium.login(username="bob", password="topsecret")
        self.assertTrue(r)
        self.selenium.get(self.live_server_url + "/bob/fields/1/appliedirrigations/")
        self.timestamp_input.wait_until_exists()

        # By default "water volume" should be selected
        self.assert_visibility(True, False, False, False, False, False)

        # Select "irrigation duration" and check
        self.irrigation_duration_radio.click()
        self.supplied_water_volume_input.wait_until_not_displayed()
        self.assert_visibility(False, True, True, False, False, False)

        # Select "flowmeter" and check
        self.flowmeter_radio.click()
        self.supplied_duration_input.wait_until_not_displayed()
        self.assert_visibility(False, False, False, True, True, True)


@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
class AgrifieldsMapPopupTestCase(SeleniumDataTestCase):
    map_marker = PageElement(By.CSS_SELECTOR, "img.leaflet-marker-icon")
    popup_element = PageElement(By.CSS_SELECTOR, "div.leaflet-popup")

    def test_popup(self):
        # Visit agrifields list page
        r = self.selenium.login(username="bob", password="topsecret")
        self.assertTrue(r)
        self.selenium.get(self.live_server_url + "/bob/fields/")
        self.map_marker.wait_until_exists()

        # Check that popup appears when marker is clicked
        self.assertFalse(self.popup_element.exists())
        self.map_marker.click()
        self.popup_element.wait_until_exists()
        self.assertTrue(self.popup_element.is_displayed())


class TelemetricFlowmeterViewMixinTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="topsecret")
        self.bob = User.objects.create_user(username="bob", password="topsecret")
        self.agrifield = mommy.make(models.Agrifield, id=1337, owner=self.bob)
        mommy.make(models.Agrifield, id=1338, owner=self.alice)
        self.client.login(username="bob", password="topsecret")
        self.post_data = {
            "LoRA_ARTA-agrifield": 1337,
            "flowmeter_type": "LoRA_ARTA",
            "LoRA_ARTA-device_id": "123",
            "LoRA_ARTA-flowmeter_water_percentage": 50,
            "LoRA_ARTA-conversion_rate": 8,
            "LoRA_ARTA-report_frequency_in_minutes": 15,
        }

    def test_create_flowmeter(self):
        self.assertFalse(hasattr(self.agrifield, "lora_artaflowmeter"))
        response = self.client.post(
            "/bob/fields/1337/appliedirrigations/", data=self.post_data
        )
        self.assertEqual(response.status_code, 302)
        agrifield = models.Agrifield.objects.get(id=self.agrifield.id)
        self.assertTrue(hasattr(agrifield, "lora_artaflowmeter"))

        created_flowmeter = agrifield.lora_artaflowmeter
        self.assertEqual(created_flowmeter.device_id, "123"),
        self.assertEqual(created_flowmeter.flowmeter_water_percentage, 50),
        self.assertEqual(created_flowmeter.conversion_rate, 8),
        self.assertEqual(created_flowmeter.report_frequency_in_minutes, 15),

    def test_create_flowmeter_non_existing_agrifield(self):
        response = self.client.post(
            "/bob/fields/7654/appliedirrigations/", data=self.post_data
        )
        self.assertEqual(response.status_code, 404)

    def test_create_flowmeter_non_owned_agrifield(self):
        response = self.client.post(
            "/alice/fields/1338/appliedirrigations/", data=self.post_data
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_flowmeter(self):
        mommy.make(models.LoRA_ARTAFlowmeter, agrifield=self.agrifield)
        response = self.client.post(
            "/bob/fields/1337/appliedirrigations/", data={"flowmeter_type": ""}
        )
        assert response.status_code == 302
        self.assertFalse(
            models.LoRA_ARTAFlowmeter.objects.filter(agrifield=self.agrifield).exists()
        )
