from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from model_mommy import mommy

from aira.models import Agrifield, AppliedIrrigation, Profile


class RedirectViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(username="alice", password="topsecret")
        cls.bob = User.objects.create_user(username="bob", password="topsecret")
        cls.bob_profile_id = Profile.objects.get(user=cls.bob).id
        cls.agrifield = mommy.make(Agrifield, owner=cls.bob, id=42, area=5000)
        mommy.make(
            AppliedIrrigation, agrifield=cls.agrifield, id=201, supplied_water_volume=50
        )

    def test_agrifield_list_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/home/bob/")
        self.assertRedirects(response, "/bob/fields/", status_code=301)

    def test_myfields_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/home/")
        self.assertRedirects(
            response,
            "/myfields/",
            status_code=301,
            target_status_code=302,
        )

    def test_agrifield_report_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/advice/42/")
        self.assertRedirects(response, "/bob/fields/42/report/", status_code=301)

    def test_agrifield_report_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/advice/42/")
        self.assertEqual(response.status_code, 404)

    def test_agrifield_create_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/create_agrifield/bob/")
        self.assertRedirects(response, "/bob/fields/create/", status_code=301)

    def test_agrifield_update_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/update_agrifield/42/")
        self.assertRedirects(response, "/bob/fields/42/edit/", status_code=301)

    def test_agrifield_update_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/update_agrifield/42/")
        self.assertEqual(response.status_code, 404)

    def test_agrifield_delete_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/delete_agrifield/42/")
        self.assertRedirects(response, "/bob/fields/42/delete/", status_code=301)

    def test_agrifield_delete_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/delete_agrifield/42/")
        self.assertEqual(response.status_code, 404)

    def test_agrifield_irrigation_performance_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/irrigation-performance-chart/42/")
        self.assertRedirects(response, "/bob/fields/42/performance/", status_code=301)

    def test_agrifield_irrigation_performance_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/irrigation-performance-chart/42/")
        self.assertEqual(response.status_code, 404)

    @mock.patch("aira.models.Agrifield.results")
    def test_agrifield_irrigation_performance_download_redirect_view(self, m):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/download-irrigation-performance/42/")
        self.assertRedirects(
            response, "/bob/fields/42/performance/download/", status_code=301
        )

    def test_agrifield_irrigation_performnc_download_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/download-irrigation-performance/42/")
        self.assertEqual(response.status_code, 404)

    @mock.patch("aira.models.Agrifield.get_point_timeseries")
    def test_agrifield_timeseries_redirect_view(self, m):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/agrifield/42/timeseries/temperature/")
        self.assertRedirects(
            response, "/bob/fields/42/timeseries/temperature/", status_code=301
        )

    def test_agrifield_timeseries_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/agrifield/42/timeseries/temperature/")
        self.assertEqual(response.status_code, 404)

    def test_agrifield_soil_analysis_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/agrifield/42/soil_analysis/")
        self.assertRedirects(
            response,
            "/bob/fields/42/soil_analysis/",
            status_code=301,
            target_status_code=404,  # Because we haven't created a test file
        )

    def test_agrifield_soil_analysis_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/agrifield/42/soil_analysis/")
        self.assertEqual(response.status_code, 404)

    def test_agrifield_applied_irrigations_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/create_irrigationlog/42/")
        self.assertRedirects(
            response, "/bob/fields/42/appliedirrigations/", status_code=301
        )

    def test_agrifield_applied_irrigations_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/create_irrigationlog/42/")
        self.assertEqual(response.status_code, 404)

    def test_agrifield_applied_irrigation_edit_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/update_irrigationlog/201/")
        self.assertRedirects(
            response, "/bob/fields/42/appliedirrigations/201/edit/", status_code=301
        )

    def test_agrifield_applied_irrigation_edit_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/update_irrigationlog/201/")
        self.assertEqual(response.status_code, 404)

    def test_agrifield_applied_irrigation_delete_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/delete_irrigationlog/201/")
        self.assertRedirects(
            response, "/bob/fields/42/appliedirrigations/201/delete/", status_code=301
        )

    def test_agrifield_applied_irrigation_delete_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/delete_irrigationlog/201/")
        self.assertEqual(response.status_code, 404)

    def test_edit_profile_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get(f"/update_profile/{self.bob_profile_id}/")
        self.assertRedirects(response, "/accounts/edit_profile/bob/", status_code=301)

    def test_edit_profile_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get(f"/update_profile/{self.bob_profile_id}/")
        self.assertEqual(response.status_code, 404)

    def test_delete_user_redirect_view(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get(f"/delete_user/{self.bob.id}/")
        self.assertRedirects(response, "/accounts/delete_user/bob/", status_code=301)

    def test_delete_user_wrong_username_redirect_view(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get(f"/delete_user/{self.bob.id}/")
        self.assertEqual(response.status_code, 404)
