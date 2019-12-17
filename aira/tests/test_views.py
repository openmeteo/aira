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
from django.test import TestCase, override_settings

import pandas as pd
import pytz
from django_selenium_clean import PageElement, SeleniumTestCase
from model_mommy import mommy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

from aira.models import Agrifield, AppliedIrrigation
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


class TestAgrifieldListView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            id=55, username="bob", password="topsecret"
        )
        self.user.save()

    def test_home_view_denies_anynomous(self):
        resp = self.client.get("/home/", follow=True)
        self.assertRedirects(resp, "/accounts/login/?next=/home/")

    def test_home_view_loads_user(self):
        self.client.login(username="bob", password="topsecret")
        resp = self.client.get("/home/")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "aira/home/main.html")


class UpdateAgrifieldViewTestCase(DataTestCase):
    def setUp(self):
        super().setUp()
        self._make_request()

    def _make_request(self):
        self.client.login(username="bob", password="topsecret")
        self.response = self.client.get(
            "/update_agrifield/{}/".format(self.agrifield.id)
        )

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


class CreateAgrifieldViewTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            id=54, username="alice", password="topsecret"
        )
        self.client.login(username="alice", password="topsecret")
        self.response = self.client.get("/create_agrifield/alice/")

    def test_status_code(self):
        self.assertEqual(self.response.status_code, 200)


class AgrifieldTimeseriesViewTestCase(TestCase):
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
            Agrifield, name="hello", location=Point(23, 38), owner=self.alice
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
                "/agrifield/{}/timeseries/temperature/".format(self.agrifield.id)
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


class DownloadSoilAnalysisViewTestCase(TestCase, RandomMediaRootMixin):
    def setUp(self):
        self.override_media_root()
        self.alice = User.objects.create_user(
            id=54, username="alice", password="topsecret"
        )
        self.agrifield = mommy.make(Agrifield, id=1, owner=self.alice)
        self.agrifield.soil_analysis.save("somefile", ContentFile("hello world"))
        self.client.login(username="alice", password="topsecret")
        self.response = self.client.get("/agrifield/1/soil_analysis/")

    def tearDown(self):
        self.end_media_root_override()

    def test_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_content(self):
        content = b""
        for x in self.response.streaming_content:
            content += x
        self.assertEqual(content, b"hello world")


class RecommendationViewTestCase(DataTestCase):
    def _make_request(self):
        self.client.login(username="bob", password="topsecret")
        self.response = self.client.get("/recommendation/{}/".format(self.agrifield.id))

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
            self.response, "<b>Soil moisture at saturation (Θ<sub>s</sub>):</b> 50.0%"
        )

    def test_response_contains_custom_theta_s(self):
        self._update_agrifield(use_custom_parameters=True, custom_thetaS=0.424)
        self._make_request()
        self.assertContains(
            self.response, "<b>Soil moisture at saturation (Θ<sub>s</sub>):</b> 42.4%"
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
            AppliedIrrigation,
            agrifield=self.agrifield,
            timestamp=tz.localize(dt.datetime(2019, 9, 11, 17, 23)),
            supplied_water_volume=100.5,
        )
        self._make_request()
        self.assertContains(
            self.response, "<b>Last recorded irrigation:</b> 11/09/2019 17:00"
        )
        self.assertContains(self.response, "<b>Applied water (m³):</b> 100.5")

    def test_response_contains_last_irrigation_with_unspecified_applied_water(self):
        tz = pytz.timezone(settings.TIME_ZONE)
        mommy.make(
            AppliedIrrigation,
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
            "<b>Applied water (m³):</b> 93.2 "
            "(Irrigation water is estimated using system's "
            "default parameters.)",
        )


class RemoveSupervisedUserTestCase(DataTestCase):
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

    def test_supervised_users_list_contains_charlie(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/home/")
        self.assertContains(
            response, '<a href="/home/charlie/">charlie (Charlie Clark)</a>', html=True
        )

    def test_remove_charlie_from_supervised(self):
        assert User.objects.get(username="charlie").profile.supervisor is not None
        self.client.login(username="bob", password="topsecret")
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": "56"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(User.objects.get(username="charlie").profile.supervisor)

    def test_attempting_to_remove_charlie_when_not_logged_in_returns_404(self):
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": self.charlie.id}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(User.objects.get(username="charlie").profile.supervisor)

    def test_attempting_to_remove_charlie_when_logged_in_as_david_returns_404(self):
        self.client.login(username="david", password="topsecret")
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": self.charlie.id}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(User.objects.get(username="charlie").profile.supervisor)

    def test_attempting_to_remove_when_already_removed_returns_404(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": self.david.id}
        )
        self.assertEqual(response.status_code, 404)

    def test_attempting_to_remove_garbage_id_returns_404(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": "garbage"}
        )
        self.assertEqual(response.status_code, 404)

    def test_posting_without_parameters_returns_404(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.post("/supervised_user/remove/")
        self.assertEqual(response.status_code, 404)


class ProfileViewsTestCase(TestCase):
    def setUp(self):
        self.bob = User.objects.create_user(id=55, username="bob", password="topsecret")
        self.bob.profile.first_name = "Bob"
        self.bob.profile.last_name = "Brown"
        self.bob.profile.save()
        self.client.login(username="bob", password="topsecret")

    def test_get_update_view(self):
        response = self.client.get("/update_profile/{}/".format(self.bob.profile.id))
        self.assertContains(response, "Bob")

    def test_get_delete_confirmation(self):
        response = self.client.get("/delete_user/55/")
        self.assertContains(response, "Bob")

    def test_confirm_delete(self):
        response = self.client.post("/delete_user/55/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username="bob").exists())


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
            AppliedIrrigation,
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
        response = self.client.get("/home/")
        self.assertNotContains(response, self.message)

    def test_warning_if_outside_period(self):
        self._setup_results_between(dt.datetime(2019, 3, 15), dt.datetime(2019, 9, 15))
        response = self.client.get("/home/")
        self.assertContains(response, self.message)

    def test_no_warning_if_inside_period(self):
        self._setup_results_between(dt.datetime(2019, 3, 15), dt.datetime(2019, 12, 15))
        response = self.client.get("/home/")
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
    datetimepicker_2 = PageElement(
        By.XPATH, '//div[@class="datetimepicker-days"]//td[text()="2"]'
    )

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

        self.date_input_element.wait_until_exists()
        self.date_input_element.click()
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


class IrrigationPerformanceChartTestCase(DataTestCase):
    def setUp(self):
        super().setUp()
        self.results = self.agrifield.execute_model()
        self.client.login(username="bob", password="topsecret")
        self.response = self.client.get(
            f"/irrigation-performance-chart/{self.agrifield.id}/"
        )
        assert self.response.status_code == 200
        self.series = self._extract_series_from_javascript(
            self.response.content.decode()
        )

    _series_regexp = r"""
        \sseries:\s* # "series:" preceded by space and followed by optional whitespace.
        (?P<series>
            \[\s*              # Bracket that starts the list.
            ({[^}]*}\s*,?\s*)* # "{" plus non-"}" characters plus "}" plus optional
                               # comma, all that repeated as many times as needed.
            \s*\]              # Bracket that ends the list.
        )
    """

    def _extract_series_from_javascript(self, page_content):
        m = re.search(self._series_regexp, page_content, re.VERBOSE)
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


class IrrigationPerformanceCsvTestCase(DataTestCase):
    def setUp(self):
        super().setUp()
        self.results = self.agrifield.execute_model()
        self.client.login(username="bob", password="topsecret")
        self.response = self.client.get(
            f"/download-irrigation-performance/{self.agrifield.id}/"
        )
        assert self.response.status_code == 200

    def test_applied_water_when_irrigation_specified(self):
        m = re.search(
            r"2018-03-15 23:59:00,[.\d]*,([.\d]*),",
            self.response.content.decode(),
            re.MULTILINE,
        )
        value = float(m.group(1))
        self.assertAlmostEqual(value, 250.0)

    def test_applied_water_when_irrigation_determined_automatically(self):
        m = re.search(
            r"2018-03-19 23:59:00,[.\d]*,([.\d]*),",
            self.response.content.decode(),
            re.MULTILINE,
        )
        value = float(m.group(1))
        self.assertAlmostEqual(value, 125.20833333)


class CreateAppliedIrrigationViewTestCase(TestCase):
    @patch("aira.models.Agrifield.get_applied_irrigation_defaults",)
    def test_applied_irrigation_defaults(self, mock):
        owner = User.objects.create_user(username="bob", password="topsecret")
        self.client.login(username="bob", password="topsecret")
        agrifield = mommy.make(Agrifield, owner=owner)

        mock.return_value = {
            "supplied_water_volume": 1337,
            "irrigation_type": "HELLO_WORLD",
        }
        response = self.client.get(f"/create_irrigationlog/{agrifield.id}/")
        initials = response.context["form"].initial
        self.assertEqual(initials["supplied_water_volume"], 1337)
        self.assertEqual(initials["irrigation_type"], "HELLO_WORLD")


@skipUnless(False, "This test isn't working yet")
@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
@override_settings(AIRA_MAP_DEFAULT_CENTER=(22.01, 37.99))
class MapPopupTestCase(SeleniumTestCase, DataTestCase):
    """Deactivated test awaiting transition to Leaflet.

    I wrote this test while we're still using OpenLayers to test that the meteo map
    popup works. However this is going to make a GetFeatureInfo request to some
    mapserver and it's not possible to test without mocking XMLHttpRequest.  Finding out
    how to do such mocking, would be quite some work and I thought it would be better to
    wait until we use Leaflet, because the code is likely to change much.

    The test doesn't run because it has @skipUnless(False) on top.
    """

    map_element = PageElement(By.ID, "map")
    google_maps_dismiss_button = PageElement(By.CLASS_NAME, "dismissButton")
    popup_element = PageElement(By.CLASS_NAME, "olPopup")

    def test_popup(self):
        # Visit front page and ensure there's no popup
        self.selenium.get(self.live_server_url)
        self.map_element.wait_until_exists()
        self.assertFalse(self.popup_element.exists())

        # This is a development environment, so we might get the "can't load Google
        # Maps correctly" warning; dismiss it
        if self.google_maps_dismiss_button.exists():
            self.google_maps_dismiss_button.click()
        self.google_maps_dismiss_button.wait_until_not_exists()

        # Click in the middle of the map
        x_offset = self.map_element.size["width"] / 2
        y_offset = self.map_element.size["height"] / 2
        ActionChains(self.selenium).move_to_element(
            self.selenium.find_element(By.ID, "map")
        ).move_by_offset(x_offset, y_offset).click().perform()

        # The popup should now appear
        self.popup_element.wait_until_exists()
        self.assertTrue(self.popup_element.exists())


class SeleniumDataTestCase(SetupTestDataMixin, SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self._setup_database()


@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
class AgrifieldsMapTestCase(SeleniumDataTestCase):
    map_element = PageElement(By.ID, "map")
    map_marker = PageElement(By.CSS_SELECTOR, "div.olLayerDiv image")

    def test_agrifields_map(self):
        # Visit user's agrifields list page
        r = self.selenium.login(username="bob", password="topsecret")
        self.assertTrue(r)
        self.selenium.get(self.live_server_url + "/home/")
        self.map_element.wait_until_exists()

        # Check that there is a marker on the map (it marks the agrifield)
        self.assertTrue(self.map_marker.exists())


@skipUnless(getattr(settings, "SELENIUM_WEBDRIVERS", False), "Selenium is unconfigured")
class AgrifieldEditMapTestCase(SeleniumDataTestCase):
    map_element = PageElement(By.ID, "map")
    map_marker = PageElement(By.CSS_SELECTOR, "div.olLayerDiv image")
    longitude_element = PageElement(By.ID, "id_location_0")
    latitude_element = PageElement(By.ID, "id_location_1")

    def test_agrifields_map(self):
        # Visit user's edit agrifield list page
        r = self.selenium.login(username="bob", password="topsecret")
        self.assertTrue(r)
        self.selenium.get(self.live_server_url + "/update_agrifield/1/")
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
        self.selenium.get(self.live_server_url + "/create_irrigationlog/1/")
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
    map_marker = PageElement(By.CSS_SELECTOR, "div.olLayerDiv image")
    popup_element = PageElement(By.ID, "pop")

    def test_popup(self):
        # Visit agrifields list page
        r = self.selenium.login(username="bob", password="topsecret")
        self.assertTrue(r)
        self.selenium.get(self.live_server_url + "/home/bob/")
        self.map_marker.wait_until_exists()

        # Check that popup appears when marker is clicked
        self.assertFalse(self.popup_element.exists())
        self.map_marker.click()
        self.popup_element.wait_until_exists()
        self.assertTrue(self.popup_element.is_displayed())
