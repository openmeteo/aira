from io import StringIO

from django import forms
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from captcha.fields import CaptchaField
from geowidgets import LatLonField
from registration.forms import RegistrationForm

from .models import Agrifield, AppliedIrrigation, Profile


class ProfileForm(forms.ModelForm):
    supervisor = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__supervision_question=True), required=False
    )

    class Meta:
        model = Profile
        exclude = ("user",)

        labels = {
            "first_name": _("Given name"),
            "last_name": _("Family name"),
            "address": _("Address"),
            "notification": _("Frequency of email notifications"),
            "email_language": _("Email notification language"),
            "supervisor": _("Supervisor"),
            "supervision_question": _("Consider me as supervisor for other accounts"),
        }


class DateInputWithoutYear(forms.DateInput):
    def __init__(self, attrs=None, format=None):
        if format is None:
            format = "%d/%m"
        super().__init__(attrs=attrs, format=format)

    def value_from_datadict(self, data, files, name):
        input = data.get(name)
        if input:
            day, month = input.split("/")
            return f"1970-{month}-{day}"


class AgrifieldForm(forms.ModelForm):
    location = LatLonField(
        label=_("Co-ordinates"),
        help_text=_("Longitude and latitude in decimal degrees"),
    )
    kc_stages = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label=_("Kc stages"),
        help_text=_(
            "The development stages. You can copy/paste them from a spreadsheet, "
            "two columns: stage length in days and Kc at end of stage. Copy and paste "
            "the points only, without headings. If you key them in instead, they must "
            "be one stage per line, first days then Kc, separated by tab or comma."
        ),
    )

    class Meta:
        model = Agrifield
        exclude = ("owner",)
        fields = [
            "name",
            "area",
            "location",
            "crop_type",
            "irrigation_type",
            "is_virtual",
            "use_custom_parameters",
            "custom_planting_date",
            "custom_kc_offseason",
            "custom_kc_initial",
            "kc_stages",
            "custom_irrigation_optimizer",
            "custom_root_depth_max",
            "custom_root_depth_min",
            "custom_max_allowed_depletion",
            "custom_efficiency",
            "custom_field_capacity",
            "custom_thetaS",
            "custom_wilting_point",
            "soil_analysis",
        ]
        labels = {
            "name": _("Field name"),
            "is_virtual": _("Is this a virtual field?"),
            "location": _("Co-ordinates"),
            "crop_type": _("Crop type"),
            "irrigation_type": _("Irrigation type"),
            "area": _("Irrigated area (m²)"),
            "use_custom_parameters": _("Use custom parameters"),
            "custom_planting_date": _("Planting date"),
            "custom_kc_offseason": _("Kc off-season"),
            "custom_kc_initial": _("Kc initial"),
            "kc_stages": _("Kc stages"),
            "custom_irrigation_optimizer": _("Irrigation optimizer"),
            "custom_root_depth_max": _("Estimated root depth (max)"),
            "custom_root_depth_min": _("Estimated root depth (min)"),
            "custom_max_allowed_depletion": _("Maximum allowed depletion"),
            "custom_efficiency": _("Irrigation efficiency"),
            "custom_field_capacity": _("Field capacity"),
            "custom_thetaS": _("Soil moisture at saturation"),
            "custom_wilting_point": _("Permanent wilting point"),
            "soil_analysis": _("Soil analysis document"),
        }
        widgets = {
            "custom_planting_date": DateInputWithoutYear(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["kc_stages"] = self.instance.kc_stages_str

    def clean_kc_stages(self):
        data = self.cleaned_data["kc_stages"]
        for i, row in enumerate(StringIO(data)):
            row = row.replace("\t", ",")
            try:
                items = row.split(",")
                int(items[0])
                float(items[1])
            except (ValueError, IndexError):
                raise forms.ValidationError(
                    _(
                        f'Error in line {i + 1}: "{row}" is not a valid '
                        "(ndays, kc_end) pair"
                    )
                )
        return data

    def clean_is_virtual(self):
        result = self.cleaned_data.get("is_virtual")
        if result is None:
            msg = _("You must select if field is virtual or not")
            self.add_error("is_virtual", msg)
        return result

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        self.instance.set_custom_kc_stages(self.cleaned_data["kc_stages"])
        return result


class AppliedIrrigationForm(forms.ModelForm):
    IRRIGATION_TYPE_CHOICES = [
        ("VOLUME_OF_WATER", _("Specify volume of irrigation water")),
        ("DURATION_OF_IRRIGATION", _("Specify duration of irrigation")),
        ("FLOWMETER_READINGS", _("Specify flowmeter readings")),
    ]
    irrigation_type = forms.ChoiceField(
        widget=forms.RadioSelect(), choices=IRRIGATION_TYPE_CHOICES, label=""
    )

    class Meta:
        model = AppliedIrrigation
        exclude = ("agrifield",)
        labels = {
            "timestamp": _("Date and time (YYYY-MM-DD HH:mm:ss) "),
            "supplied_water_volume": _("Volume of applied irrigation water (m³)"),
            "supplied_duration": _("Duration of irrigation (min)"),
            "supplied_flow_rate": _("Flow rate (m³/h)"),
            "flowmeter_reading_start": _("Flowmeter reading at start of irrigation"),
            "flowmeter_reading_end": _("Flowmeter reading at end of irrigation"),
            "flowmeter_water_percentage": _(
                "Percentage of water that corresponds to the flowmeter (%)"
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        irrigation_type = cleaned_data.get("irrigation_type")
        if irrigation_type == "VOLUME_OF_WATER":
            self._validate_required(["supplied_water_volume"])
        elif irrigation_type == "DURATION_OF_IRRIGATION":
            self._validate_required(["supplied_duration", "supplied_flow_rate"])
        elif irrigation_type == "FLOWMETER_READINGS":
            fields = [
                "flowmeter_reading_start",
                "flowmeter_reading_end",
                "flowmeter_water_percentage",
            ]
            self._validate_required(fields)
        return super().clean()

    def _validate_required(self, fields=[]):
        # Used to require fields dynamically (depending on other submitted values)
        for field in fields:
            if self.cleaned_data.get(field, None) is None:
                self.add_error(field, _("This field is required."))


class MyRegistrationForm(RegistrationForm):

    """
    Extension of the default registration form to include a captcha
    """

    captcha = CaptchaField(label=_("Are you human?"))
