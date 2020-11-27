from django.conf import settings
from django.contrib import admin
from django.contrib.flatpages.views import flatpage
from django.urls import include, path

from registration.backends.default.views import RegistrationView

from aira import account_views
from aira.forms import MyRegistrationForm

urlpatterns = [
    path(
        "accounts/register/",
        RegistrationView.as_view(form_class=MyRegistrationForm),
        name="registration_register",
    ),
    path(
        "accounts/edit_profile/<str:username>/",
        account_views.EditProfileView.as_view(),
        name="edit_profile",
    ),
    path(
        "accounts/delete_user/<str:username>/",
        account_views.DeleteUserView.as_view(),
        name="delete_user",
    ),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("accounts/", include("registration.backends.default.urls")),
    path("", include("aira.urls")),
    path("captcha/", include("captcha.urls")),
    path("description/", flatpage, {"url": "/description/"}, name="description"),
    path("terms-of-use/", flatpage, {"url": "/terms-of-use/"}, name="terms"),
    path("disclaimer/", flatpage, {"url": "/disclaimer/"}, name="disclaimer"),
]

# If you want to use the Django debug toolbar, then:
# 1) pip install django-debug-toolbar
# 2) Add this to aira_project/settings/local.py:
#     DEBUG = True
#     INSTALLED_APPS.append("debug_toolbar")
#     MIDDLEWARE.insert(3, "debug_toolbar.middleware.DebugToolbarMiddleware")
#     INTERNAL_IPS = ["127.0.0.1"]

use_django_debug_toolbar = (
    settings.DEBUG
    and "debug_toolbar.middleware.DebugToolbarMiddleware" in settings.MIDDLEWARE
)
if use_django_debug_toolbar:
    import debug_toolbar

    urlpatterns.insert(0, path("__debug__/", include(debug_toolbar.urls)))
