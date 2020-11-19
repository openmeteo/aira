from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import Http404
from django.urls import reverse
from django.views.generic.edit import DeleteView, UpdateView

from .forms import ProfileForm
from .models import Profile


class EditProfileView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    template_name_suffix = "/form"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user in form.fields["supervisor"].queryset:
            form.fields["supervisor"].queryset = form.fields[
                "supervisor"
            ].queryset.exclude(pk=self.request.user.id)
        return form

    def get_object(self):
        result = Profile.objects.get(user__username=self.kwargs["username"])
        if self.request.user != result.user:
            raise Http404
        return result

    def get_success_url(self):
        return reverse("agrifield-list", kwargs={"username": self.kwargs["username"]})


class DeleteUserView(LoginRequiredMixin, DeleteView):
    model = User
    template_name_suffix = "/confirm_delete"

    def get_object(self):
        result = User.objects.get(username=self.kwargs["username"])
        if self.request.user != result:
            raise Http404
        return result

    def get_success_url(self):
        return reverse("frontpage")
