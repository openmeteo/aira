import logging
from datetime import date, datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from aira.models import Profile, notification_options


class Command(BaseCommand):
    help = "Emails irrigation recommendation notifications to users."

    def handle(self, *args, **options):
        for user in User.objects.all():
            if not self.must_send_notification(user):
                continue

            # Send notification for user's own agrifields
            self.notify_user(user, user.agrifield_set.all(), user)

            # If user is a supervisor, send an additional notification to him
            # for each of the supervised users.
            for supervisee in User.objects.filter(profile__supervisor=user):
                self.notify_user(user, supervisee.agrifield_set.all(), supervisee)

    def must_send_notification(self, user):
        try:
            return notification_options[user.profile.notification][1](date.today())
        except (Profile.DoesNotExist, KeyError):
            return False

    def get_email_context(self, agrifields, user, owner):
        context = {}
        if agrifields[0].results is None:
            logging.error(
                (
                    "Internal error: No results for agrifield {} of user {}; "
                    "omitting notification for that user"
                ).format(agrifields[0].name, user)
            )
            return None
        context["owner"] = owner
        context["agrifields"] = agrifields
        context["site"] = Site.objects.get_current()
        context["user"] = user
        context["timestamp"] = datetime.now()
        context["header"] = settings.AIRA_EMAIL_HEADER
        context["footer"] = settings.AIRA_EMAIL_FOOTER
        return context

    def notify_user(self, user, agrifields, owner):
        agrifields = [f for f in agrifields if f.in_covered_area]
        if not agrifields:
            return
        logging.info(
            "Notifying user {} about the agrifields of user {}".format(user, owner)
        )
        translation.activate(user.profile.email_language)
        context = self.get_email_context(agrifields, user, owner)
        if context is None:
            return
        msg_html = render_to_string(
            "aira/email_notification/email_notification.html", context
        )
        send_mail(
            _("Irrigation status for user {}".format(str(owner))),
            "",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=msg_html,
        )
