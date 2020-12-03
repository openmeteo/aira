from django.contrib.auth.models import User
from django.test import TestCase

from bs4 import BeautifulSoup


class RegistrationViewTestCase(TestCase):
    def test_template_is_overriden(self):
        """Test that the correct template is used.

        In INSTALLED_APPS, "aira" has to go before "registration" (which has to go
        before "django.contrib.admin"), so that the registration templates are read from
        aira/templates/registration and not from django-registration-redux. This is easy
        to misconfigure, so we test it here.
        """
        response = self.client.get("/accounts/register/")
        # Check the title. django-registration-redux's default is "Register for an
        # account"
        self.assertContains(response, "<title>Registration —")


class ProfileViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bob = User.objects.create_user(id=55, username="bob", password="topsecret")
        cls.bob.profile.first_name = "Bob"
        cls.bob.profile.last_name = "Brown"
        cls.bob.profile.save()

    def setUp(self):
        self.client.login(username="bob", password="topsecret")

    def test_get_edit_view(self):
        response = self.client.get("/accounts/edit_profile/bob/")
        self.assertContains(response, "Bob")

    def test_edit_view_delete_account_button(self):
        response = self.client.get("/accounts/edit_profile/bob/")
        soup = BeautifulSoup(response.content.decode(), "html.parser")
        href = soup.find(id="btn-delete-account")["href"]
        self.assertEqual(href, "/accounts/delete_user/bob/")

    def test_get_delete_confirmation(self):
        response = self.client.get("/accounts/delete_user/bob/")
        self.assertContains(response, "Bob")

    def test_confirm_delete(self):
        response = self.client.post("/accounts/delete_user/bob/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username="bob").exists())


class ProfileLinkTestCase(TestCase):
    def setUp(self):
        self.bob = User.objects.create_user(id=55, username="bob", password="topsecret")
        self.bob.profile.first_name = "Bob"
        self.bob.profile.last_name = "Brown"
        self.bob.profile.save()
        self.client.login(username="bob", password="topsecret")

    def test_navbar_contains_profile_link(self):
        response = self.client.get("/")
        self.assertContains(response, 'href="/accounts/edit_profile/bob/"')
