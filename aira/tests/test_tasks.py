from unittest.mock import patch

from django.test import TestCase, override_settings

import requests
from model_mommy import mommy

from aira import models
from aira.tasks import _get_ttn_data, add_irrigations_from_telemetric_flowmeters


class MockResponse(requests.Response):
    def __init__(self, status_code=200, data_points=[]):
        super().__init__()
        self.status_code = status_code
        self.data_points = data_points

    def json(self):
        return self.data_points


@override_settings(
    AIRA_THE_THINGS_NETWORK_ACCESS_KEY="TOKEN",
    AIRA_THE_THINGS_NETWORK_BASE_URL="some.url",
)
class LoRA_ARTAFlowmeterTTNIntegrationTestCase(TestCase):
    def setUp(self):
        self.data_points = [
            {
                "SensorFrequency": 1,
                "device_id": "d1",
                "raw": "AAAbvAUUBvA=",
                "time": "2020-10-18T00:19:27.62050186Z",
            },
            {
                "SensorFrequency": 2,
                "device_id": "d1",
                "raw": "AAAbvAUUBvA=",
                "time": "2020-10-18T00:20:00.179529862Z",
            },
            {
                "SensorFrequency": 3,
                "device_id": "d2",
                "raw": "AAAbvAUUBvA=",
                "time": "2020-10-18T00:21:00.179529862Z",
            },
        ]

    @patch("aira.tasks.requests.get")
    def test_ttn_response_parsing(self, mocked_get):
        mocked_get.return_value = MockResponse(data_points=self.data_points)
        result = _get_ttn_data()
        expected_result = [
            {
                "sensor_frequency": 1,
                "timestamp": "2020-10-18T00:19:27.62050186Z",
                "device_id": "d1",
            },
            {
                "sensor_frequency": 2,
                "timestamp": "2020-10-18T00:20:00.179529862Z",
                "device_id": "d1",
            },
            {
                "sensor_frequency": 3,
                "timestamp": "2020-10-18T00:21:00.179529862Z",
                "device_id": "d2",
            },
        ]
        self.assertEqual(result, expected_result)

    @patch("aira.tasks.requests.get")
    def test_irrigations_created_for_correct_flowmeter(self, mocked_get):
        f1 = mommy.make(models.LoRA_ARTAFlowmeter, id=1, device_id="1")
        f2 = mommy.make(models.LoRA_ARTAFlowmeter, id=2, device_id="2")
        self.data_points[0]["device_id"] = "1"
        self.data_points[1]["device_id"] = "2"
        self.data_points[2]["device_id"] = "1"
        mocked_get.return_value = MockResponse(data_points=self.data_points)

        self.assertEqual(f1.agrifield.appliedirrigation_set.count(), 0)
        self.assertEqual(f2.agrifield.appliedirrigation_set.count(), 0)

        add_irrigations_from_telemetric_flowmeters()

        self.assertEqual(f1.agrifield.appliedirrigation_set.count(), 2)
        self.assertEqual(f2.agrifield.appliedirrigation_set.count(), 1)

    @patch("aira.tasks.requests.get")
    def test_non_existing_device_id_is_logged(self, mocked_get):
        self.data_points[0]["device_id"] = "1337"
        self.data_points[1]["device_id"] = "1337"
        self.data_points[2]["device_id"] = "1338"
        mocked_get.return_value = MockResponse(data_points=self.data_points)

        mommy.make(models.LoRA_ARTAFlowmeter, id=1337, device_id="1337")
        with patch("aira.tasks.logger.warn") as mock_log:
            self.assertEqual(mock_log.call_count, 0)
            add_irrigations_from_telemetric_flowmeters()
            mock_log.assert_called_once_with(
                "Got non-existing flowmeter with id=1338 from TTN."
            )

    @patch("aira.tasks.requests.get")
    def test_zero_sensor_frequency(self, mocked_get):
        mocked_get.return_value = MockResponse(
            data_points=[
                {
                    "SensorFrequency": 0.0,
                    "device_id": "d1",
                    "raw": "AAAbvAUUBvA=",
                    "time": "2020-10-18T00:19:27.62050186Z",
                }
            ]
        )
        result = _get_ttn_data()
        self.assertEqual(result, [])
