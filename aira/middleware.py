from django.contrib.auth.models import User
from django.http import Http404
from django.shortcuts import get_object_or_404


class PermissionsMiddleware:
    paths_not_checked_here = (
        "accounts",
        "i18n",
        "admin",
        "captcha",
        "description",
        "terms-of-use",
        "disclaimer",
        "conversion_tools",
        "try",
        "myfields",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._check_permissions(request)
        return self.get_response(request)

    def _check_permissions(self, request):
        if request.path == "/":
            return
        first_path_item = request.path.split("/")[1]
        if first_path_item in self.paths_not_checked_here:
            return
        else:
            self._check_permissions_for_username(first_path_item, request)

    def _check_permissions_for_username(self, username, request):
        url_user = get_object_or_404(User, username=username)
        allow = request.user.is_authenticated and (
            request.user == url_user
            or request.user == url_user.profile.supervisor
            or request.user.is_superuser
        )
        if not allow:
            raise Http404
