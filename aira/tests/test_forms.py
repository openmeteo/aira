from django.test import TestCase

from model_mommy import mommy

from aira import models
from aira.forms import AgrifieldForm, AppliedIrrigationForm, DateInputWithoutYear


class RegistrationFormTestCase(TestCase):
    def test_registration_form_submission(self):
        post_data = {"usename": "bob", "password": "topsecret"}
        r = self.client.post("/accounts/register/", post_data)
        self.assertEqual(r.status_code, 200)

    def test_registation_form_fails_blank_submission(self):
        r = self.client.post("/accounts/register/", {})
        self.assertFormError(r, "form", "password1", "This field is required.")


class AppliedIrrigationFormTestCase(TestCase):
    def setUp(self):
        self.data = {
            "timestamp": "2020-02-02",
        }

    def test_required_fields_with_type_volume_of_water(self):
        form_data = {**self.data, "irrigation_type": "VOLUME_OF_WATER"}
        form = AppliedIrrigationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEquals(
            form.errors, {"supplied_water_volume": ["This field is required."]}
        )

    def test_required_fields_with_type_duration_of_irrigation(self):
        form_data = {**self.data, "irrigation_type": "DURATION_OF_IRRIGATION"}
        form = AppliedIrrigationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEquals(
            form.errors,
            {
                "supplied_duration": ["This field is required."],
                "supplied_flow_rate": ["This field is required."],
            },
        )

    def test_required_fields_with_type_flowmeter_readings(self):
        form_data = {**self.data, "irrigation_type": "FLOWMETER_READINGS"}
        form = AppliedIrrigationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEquals(
            form.errors,
            {
                "flowmeter_water_percentage": ["This field is required."],
                "flowmeter_reading_start": ["This field is required."],
                "flowmeter_reading_end": ["This field is required."],
            },
        )


class DateInputWithoutYearTestCase(TestCase):
    def setUp(self):
        self.widget = DateInputWithoutYear()

    def test_format(self):
        self.assertEqual(self.widget.format, "%d/%m")

    def test_value_from_datadict(self):
        data = {"mydate": "03/05"}
        result = self.widget.value_from_datadict(data=data, files=None, name="mydate")
        self.assertEqual(result, "1970-05-03")

    def test_empty_value_from_datadict(self):
        result = self.widget.value_from_datadict(data={}, files=None, name="mydate")
        self.assertIsNone(result)


class AgrifieldFormCleanKcStagesTestCase(TestCase):
    def setUp(self):
        self.agrifield = mommy.make(models.Agrifield)
        self.post_data = {
            "name": "Great tomatoes",
            "location_0": 20.87591,
            "location_1": 39.14904,
            "crop_type": self.agrifield.crop_type.id,
            "irrigation_type": self.agrifield.irrigation_type.id,
            "is_virtual": False,
            "area": 15,
        }

    def test_validates_without_kc_stages(self):
        form = AgrifieldForm(self.post_data, instance=self.agrifield)
        self.assertTrue(form.is_valid())

    def _check_validation_error(self, kc_stages, expected_message):
        self.post_data["kc_stages"] = kc_stages
        form = AgrifieldForm(self.post_data, instance=self.agrifield)
        self.assertFalse(form.is_valid())
        self.assertIn(expected_message, form.errors["kc_stages"][0])

    def test_validation_error_when_kc_stages_is_garbage(self):
        self._check_validation_error(
            kc_stages="garbage",
            expected_message='"garbage" is not a valid (ndays, kc_end) pair',
        )

    def test_validation_error_when_kc_stages_has_wrong_ndays(self):
        self._check_validation_error(
            kc_stages="15.2, 0.8",
            expected_message='"15.2, 0.8" is not a valid (ndays, kc_end) pair',
        )

    def test_validation_error_when_kc_end_is_absent(self):
        self._check_validation_error(
            kc_stages="15", expected_message='"15" is not a valid (ndays, kc_end) pair',
        )

    def test_validation_error_when_kc_end_is_wrong(self):
        self._check_validation_error(
            kc_stages="15, a",
            expected_message='"15, a" is not a valid (ndays, kc_end) pair',
        )

    def test_validates_when_correct_data_with_tabs(self):
        self.post_data["kc_stages"] = "15\t0.9"
        form = AgrifieldForm(self.post_data, instance=self.agrifield)
        self.assertTrue(form.is_valid())

    def test_validates_when_correct_data_with_commas(self):
        self.post_data["kc_stages"] = "15, 0.9"
        form = AgrifieldForm(self.post_data, instance=self.agrifield)
        self.assertTrue(form.is_valid())

    def test_validates_when_correct_data_with_commas_and_tabs(self):
        self.post_data["kc_stages"] = "15\t0.9\n25, 0.8"
        form = AgrifieldForm(self.post_data, instance=self.agrifield)
        self.assertTrue(form.is_valid())


class AgrifieldFormInitializeTestCase(TestCase):
    def setUp(self):
        self.agrifield = mommy.make(models.Agrifield)
        self._make_kc_stage(order=1, ndays=5, kc_end=0.1)
        self._make_kc_stage(order=2, ndays=4, kc_end=0.2)
        self._make_kc_stage(order=3, ndays=3, kc_end=0.3)

    def _make_kc_stage(self, *, order, ndays, kc_end):
        mommy.make(
            models.AgrifieldCustomKcStage,
            agrifield=self.agrifield,
            order=order,
            ndays=ndays,
            kc_end=kc_end,
        )

    def test_kc_stages_initial_value(self):
        form = AgrifieldForm(instance=self.agrifield)
        self.assertEqual(form.initial["kc_stages"], "5\t0.1\n4\t0.2\n3\t0.3")


class AgrifieldFormSaveTestCase(TestCase):
    def setUp(self):
        self.agrifield = mommy.make(models.Agrifield)
        self.post_data = {
            "name": "Great tomatoes",
            "location_0": 20.87591,
            "location_1": 39.14904,
            "crop_type": self.agrifield.crop_type.id,
            "irrigation_type": self.agrifield.irrigation_type.id,
            "is_virtual": False,
            "area": 15,
            "kc_stages": "15\t0.9\n25\t0.8",
        }
        form = AgrifieldForm(self.post_data, instance=self.agrifield)
        assert form.is_valid()
        form.save()
        self.kc_stages = models.AgrifieldCustomKcStage.objects.order_by("order")

    def test_first_row(self):
        row = self.kc_stages[0]
        self.assertEqual(row.order, 1)
        self.assertEqual(row.ndays, 15)
        self.assertAlmostEqual(row.kc_end, 0.9)

    def test_second_row(self):
        row = self.kc_stages[1]
        self.assertEqual(row.order, 2)
        self.assertEqual(row.ndays, 25)
        self.assertAlmostEqual(row.kc_end, 0.8)
