from unittest import mock

from django.core import mail, management
from django.test import override_settings

from aira.tests.test_agrifield import DataTestCase


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class SendNotificationsTestCase(DataTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user.email = "bob@antonischristofides.com"
        cls.user.save()
        cls.user.profile.notification = "D"
        cls.user.profile.save()
        cls.agrifield.execute_model()

    # We don't let send_notifications use logging, otherwise the rest of the
    # unit tests somehow start polluting the output with messages
    @mock.patch("aira.management.commands.send_notifications.logging")
    def setUp(self, m):
        management.call_command("send_notifications")

    def test_has_sent_email(self):
        self.assertTrue(len(mail.outbox) > 0)
