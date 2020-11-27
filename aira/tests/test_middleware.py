from django.contrib.auth.models import User
from django.test import TestCase

from model_mommy import mommy

from aira import models


class PermissionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._create_users()
        cls.agrifield = mommy.make(models.Agrifield, owner=cls.charlie)

    @classmethod
    def _create_users(cls):
        cls.alice = cls._create_user("alice", is_superuser=True)
        cls.bob = cls._create_user("bob", is_superuser=False)
        cls.charlie = cls._create_user(
            "charlie", is_superuser=False, supervisor=cls.bob
        )
        cls.david = cls._create_user("david", is_superuser=False)

    @classmethod
    def _create_user(cls, username, is_superuser, supervisor=None):
        user = User.objects.create_user(
            username=username, password="topsecret", is_superuser=is_superuser
        )
        user.profile.supervisor = supervisor
        user.profile.save()
        return user


class PermissionsMiddlewareTestCase(PermissionsTestCase):
    def test_administrator_can_access(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/charlie/fields/")
        self.assertEqual(response.status_code, 200)

    def test_supervisor_can_access(self):
        self.client.login(username="bob", password="topsecret")
        response = self.client.get("/charlie/fields/")
        self.assertEqual(response.status_code, 200)

    def test_owner_can_access(self):
        self.client.login(username="charlie", password="topsecret")
        response = self.client.get("/charlie/fields/")
        self.assertEqual(response.status_code, 200)

    def test_other_cannot_access(self):
        self.client.login(username="david", password="topsecret")
        response = self.client.get("/charlie/fields/")
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_user_fails(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/nonexistent/fields/")
        self.assertEqual(response.status_code, 404)
