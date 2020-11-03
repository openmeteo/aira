import csv
import datetime as dt
import os
from glob import glob

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic.base import RedirectView, TemplateView, View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView

import pandas as pd

from .forms import AgrifieldForm, AppliedIrrigationForm
from .models import Agrifield, AppliedIrrigation, Profile


class CheckUsernameMixin:
    """Check that the username in the URL is correct.

    Many views have a URL of the form "/{username}/fields/{agrifield_id}/{remainder}".
    In these cases, the agrifield is fully specified with the {agrifield_id}; the
    {username} is not required. So we want to make sure you can't arrive at the field
    through a wrong username.
    """

    def get_object(self, *args, **kwargs):
        agrifield = self.get_agrifield()
        if self.model == Agrifield:
            return agrifield
        result = super().get_object()
        if result.agrifield != agrifield:
            raise Http404
        return result

    def get_agrifield(self):
        agrifield_id = self.kwargs.get("agrifield_id") or self.kwargs.get("pk")
        return get_object_or_404(
            Agrifield, pk=agrifield_id, owner__username=self.kwargs["username"]
        )


class IrrigationPerformanceView(CheckUsernameMixin, DetailView):
    model = Agrifield
    template_name = "aira/performance_chart/main.html"

    def get_context_data(self, **kwargs):
        self.object.can_edit(self.request.user)
        self.context = super().get_context_data(**kwargs)
        if not self.object.results:
            return self.context
        self._get_sum_applied_irrigation()
        self._get_percentage_diff()
        return self.context

    def _get_sum_applied_irrigation(self):
        results = self.object.results
        sum_applied_irrigation = results["timeseries"].applied_irrigation
        sum_applied_irrigation = pd.to_numeric(sum_applied_irrigation)
        sum_applied_irrigation[sum_applied_irrigation.isna()] = 0
        sum_applied_irrigation = sum_applied_irrigation.sum()
        self.context["sum_applied_irrigation"] = sum_applied_irrigation

    def _get_percentage_diff(self):
        results = self.object.results
        sum_ifinal_theoretical = results["timeseries"].ifinal_theoretical.sum()
        sum_applied_irrigation = self.context["sum_applied_irrigation"]
        if sum_ifinal_theoretical >= 0.1:
            self.context["percentage_diff"] = round(
                (sum_applied_irrigation - sum_ifinal_theoretical)
                / sum_ifinal_theoretical
                * 100
            )
        else:
            self.context["percentage_diff"] = _("N/A")


class IrrigationPerformanceCsvView(CheckUsernameMixin, View):
    def get(self, *args, **kwargs):
        f = self.get_agrifield()
        response = HttpResponse(content_type="text/csv")
        response[
            "Content-Disposition"
        ] = 'attachment; filename="{}-performance.csv"'.format(f.id)
        f.can_edit(self.request.user)
        writer = csv.writer(response)
        writer.writerow(
            [
                "Date",
                "Estimated Irrigation Water Amount",
                "Applied Irrigation Water Amount",
                "Effective precipitation",
            ]
        )
        writer.writerow(["", "amount (mm)", "amount (mm)", "amount (mm)"])
        for date, row in f.results["timeseries"].iterrows():
            writer.writerow(
                [
                    date,
                    row.ifinal_theoretical,
                    row.applied_irrigation if row.applied_irrigation else 0,
                    row.effective_precipitation,
                ]
            )
        return response


class DemoView(TemplateView):
    def get(self, request):
        user = authenticate(username="demo", password="demo")
        login(request, user)
        return redirect("agrifield-list", user)


class ConversionToolsView(LoginRequiredMixin, TemplateView):
    template_name = "aira/tools/main.html"


class FrontPageView(TemplateView):
    template_name = "aira/frontpage/main.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filenames = sorted(
            glob(os.path.join(settings.AIRA_DATA_HISTORICAL, "daily_rain-*.tif"))
        )
        try:
            context["start_date"] = self._get_date_from_filename(filenames[0])
            context["end_date"] = self._get_date_from_filename(filenames[-1])
        except IndexError:
            context["start_date"] = dt.date(2019, 1, 1)
            context["end_date"] = dt.date(2019, 1, 3)
        return context

    def _get_date_from_filename(self, filename):
        datestr = os.path.basename(filename).split(".")[0].partition("-")[2]
        y, m, d = (int(x) for x in datestr.split("-"))
        return dt.date(y, m, d)


class AgrifieldListView(LoginRequiredMixin, TemplateView):
    template_name = "aira/agrifield_list/main.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Load data paths
        url_username = kwargs.get("username")
        context["url_username"] = kwargs.get("username")
        if kwargs.get("username") is None:
            url_username = self.request.user
            context["url_username"] = self.request.user
        # User is url_slug <username>
        user = User.objects.get(username=url_username)

        # Fetch models.Profile(User)
        try:
            context["profile"] = Profile.objects.get(user=self.request.user)
        except Profile.DoesNotExist:
            context["profile"] = None
        # Fetch models.Agrifield(User)
        try:
            agrifields = Agrifield.objects.filter(owner=user).all()
            for f in agrifields:
                # Check if user is allowed or 404
                f.can_edit(self.request.user)
            context["agrifields"] = agrifields
            context["fields_count"] = len(agrifields)
        except Agrifield.DoesNotExist:
            context["agrifields"] = None
        return context


class MyFieldsView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return reverse(
                "agrifield-list", kwargs={"username": self.request.user.username}
            )
        else:
            raise Http404


class AgrifieldReportView(CheckUsernameMixin, LoginRequiredMixin, DetailView):
    model = Agrifield
    template_name = "aira/agrifield_report/main.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.can_edit(self.request.user)
        return context


class CreateAgrifieldView(LoginRequiredMixin, CreateView):
    model = Agrifield
    form_class = AgrifieldForm
    template_name = "aira/agrifield_edit/main.html"

    def form_valid(self, form):
        user = User.objects.get(username=self.kwargs["username"])
        form.instance.owner = user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("agrifield-list", kwargs={"username": self.kwargs["username"]})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            url_username = self.kwargs["username"]
            user = User.objects.get(username=url_username)
            context["agrifields"] = Agrifield.objects.filter(owner=user).all()
            context["agrifield_owner"] = user

        except Agrifield.DoesNotExist:
            context["agrifields"] = None
        return context


class UpdateAgrifieldView(CheckUsernameMixin, LoginRequiredMixin, UpdateView):
    model = Agrifield
    form_class = AgrifieldForm
    template_name = "aira/agrifield_edit/main.html"

    def get_success_url(self):
        field = Agrifield.objects.get(pk=self.kwargs["pk"])
        return reverse("agrifield-list", kwargs={"username": field.owner})

    def get_context_data(self, **kwargs):
        self.object.can_edit(self.request.user)
        context = super().get_context_data(**kwargs)
        context["agrifield_owner"] = self.object.owner
        return context


class DeleteAgrifieldView(CheckUsernameMixin, LoginRequiredMixin, DeleteView):
    model = Agrifield
    form_class = AgrifieldForm
    template_name = "aira/agrifield_delete/confirm.html"

    def get_success_url(self):
        field = Agrifield.objects.get(pk=self.kwargs["pk"])
        return reverse("agrifield-list", kwargs={"username": field.owner})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        afieldobj = Agrifield.objects.get(pk=self.kwargs["pk"])
        afieldobj.can_edit(self.request.user)
        return context


class AppliedIrrigationsView(CheckUsernameMixin, LoginRequiredMixin, CreateView):
    model = AppliedIrrigation
    form_class = AppliedIrrigationForm
    template_name_suffix = "/create"

    def get_success_url(self):
        field = Agrifield.objects.get(pk=self.kwargs.get("agrifield_id"))
        return reverse("agrifield-list", kwargs={"username": field.owner})

    def form_valid(self, form):
        form.instance.agrifield = Agrifield.objects.get(
            pk=self.kwargs.get("agrifield_id")
        )
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        self.agrifield = self.get_agrifield()
        self.agrifield.can_edit(request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["agrifield"] = self.agrifield
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        initial_values = self.agrifield.get_applied_irrigation_defaults()
        kwargs["initial"] = {**kwargs["initial"], **initial_values}
        return kwargs


class AppliedIrrigationViewMixin:
    model = AppliedIrrigation
    form_class = AppliedIrrigationForm

    def get_object(self):
        applied_irrigation = super().get_object()
        applied_irrigation.agrifield.can_edit(self.request.user)
        return applied_irrigation

    def get_success_url(self):
        return reverse(
            "applied-irrigations",
            kwargs={
                "username": self.object.agrifield.owner,
                "agrifield_id": self.object.agrifield.id,
            },
        )


class UpdateAppliedIrrigationView(
    CheckUsernameMixin, LoginRequiredMixin, AppliedIrrigationViewMixin, UpdateView
):
    template_name_suffix = "/update"


class DeleteAppliedIrrigationView(
    CheckUsernameMixin, LoginRequiredMixin, AppliedIrrigationViewMixin, DeleteView
):
    template_name_suffix = "/confirm_delete"


def remove_supervisee_from_user_list(request, username):
    if request.method != "POST" or username != request.user.username:
        raise Http404
    try:
        supervisee_profile = Profile.objects.get(
            user_id=int(request.POST.get("supervisee_id")),
            supervisor=request.user,
        )
    except (TypeError, ValueError, Profile.DoesNotExist):
        raise Http404
    supervisee_profile.supervisor = None
    supervisee_profile.save()
    return HttpResponseRedirect(
        reverse("supervisees", kwargs={"username": request.user.username})
    )


class SuperviseesView(LoginRequiredMixin, ListView):
    model = Profile
    template_name = "aira/supervisees/main.html"

    def get_queryset(self):
        qs = super().get_queryset().filter(supervisor=self.request.user)
        qs = qs.order_by("first_name", "last_name")
        return qs


class AgrifieldTimeseriesView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        agrifield = get_object_or_404(Agrifield, pk=kwargs.get("agrifield_id"))
        if agrifield.owner.username != self.kwargs["username"]:
            raise Http404
        variable = kwargs.get("variable")
        filename = agrifield.get_point_timeseries(variable)
        return FileResponse(
            open(filename, "rb"), as_attachment=True, content_type="text_csv"
        )


class DownloadSoilAnalysisView(CheckUsernameMixin, LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        agrifield = self.get_agrifield()
        agrifield.can_edit(self.request.user)
        if not agrifield.soil_analysis:
            raise Http404
        return FileResponse(agrifield.soil_analysis, as_attachment=True)
