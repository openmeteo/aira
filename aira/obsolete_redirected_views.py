from django.contrib.auth.models import User
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic.base import RedirectView

from . import models


class AgrifieldWithUsernameRedirectView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        agrifield = get_object_or_404(
            models.Agrifield, pk=kwargs.get(self.old_agrifield_id_kwarg)
        )
        agrifield.can_edit(self.request.user)
        username = agrifield.owner.username
        del kwargs[self.old_agrifield_id_kwarg]
        kwargs[self.new_agrifield_id_kwarg] = agrifield.id
        return super().get_redirect_url(username=username, **kwargs)


class RecommendationRedirectView(AgrifieldWithUsernameRedirectView):
    permanent = True
    pattern_name = "agrifield-report"
    old_agrifield_id_kwarg = "pk"
    new_agrifield_id_kwarg = "pk"


class UpdateAgrifieldRedirectView(AgrifieldWithUsernameRedirectView):
    permanent = True
    pattern_name = "agrifield-update"
    old_agrifield_id_kwarg = "pk"
    new_agrifield_id_kwarg = "pk"


class DeleteAgrifieldRedirectView(AgrifieldWithUsernameRedirectView):
    permanent = True
    pattern_name = "agrifield-delete"
    old_agrifield_id_kwarg = "pk"
    new_agrifield_id_kwarg = "pk"


class IrrigationPerformanceRedirectView(AgrifieldWithUsernameRedirectView):
    permanent = True
    pattern_name = "agrifield-irrigation-performance"
    old_agrifield_id_kwarg = "pk"
    new_agrifield_id_kwarg = "pk"


class IrrigationPerformanceDownloadRedirectView(AgrifieldWithUsernameRedirectView):
    permanent = True
    pattern_name = "agrifield-irrigation-performance-download"
    old_agrifield_id_kwarg = "pk"
    new_agrifield_id_kwarg = "pk"


class AgrifieldTimeseriesRedirectView(AgrifieldWithUsernameRedirectView):
    permanent = True
    pattern_name = "agrifield-timeseries"
    old_agrifield_id_kwarg = "agrifield_id"
    new_agrifield_id_kwarg = "agrifield_id"


class DownloadSoilAnalysisRedirectView(AgrifieldWithUsernameRedirectView):
    permanent = True
    pattern_name = "agrifield-soil-analysis"
    old_agrifield_id_kwarg = "agrifield_id"
    new_agrifield_id_kwarg = "agrifield_id"


class AppliedIrrigationsRedirectView(AgrifieldWithUsernameRedirectView):
    permanent = True
    pattern_name = "applied-irrigations"
    old_agrifield_id_kwarg = "pk"
    new_agrifield_id_kwarg = "agrifield_id"


class AppliedIrrigationDetailMixin:
    def get_redirect_url(self, *args, **kwargs):
        user = self.request.user
        applied_irrigation = get_object_or_404(
            models.AppliedIrrigation, id=kwargs["pk"]
        )
        agrifield = get_object_or_404(
            models.Agrifield, pk=applied_irrigation.agrifield_id, owner=user
        )
        return super().get_redirect_url(
            username=user.username, agrifield_id=agrifield.id, pk=applied_irrigation.id
        )


class AppliedIrrigationEditRedirectView(AppliedIrrigationDetailMixin, RedirectView):
    permanent = True
    pattern_name = "applied-irrigation-update"


class AppliedIrrigationDeleteRedirectView(AppliedIrrigationDetailMixin, RedirectView):
    permanent = True
    pattern_name = "applied-irrigation-delete"


class EditProfileRedirectView(RedirectView):
    permanent = True
    pattern_name = "edit_profile"

    def get_redirect_url(self, *args, **kwargs):
        user = get_object_or_404(models.Profile, pk=kwargs["pk"]).user
        if user != self.request.user:
            raise Http404
        return super().get_redirect_url(username=user.username)


class DeleteUserRedirectView(RedirectView):
    permanent = True
    pattern_name = "delete_user"

    def get_redirect_url(self, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs["pk"])
        if user != self.request.user:
            raise Http404
        return super().get_redirect_url(username=user.username)
