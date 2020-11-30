import logging

from django.conf import settings
from django.core.cache import cache

import requests

from aira.celery import app
from aira.models import LoRA_ARTAFlowmeter

logger = logging.getLogger(__name__)


@app.task
def calculate_agrifield(agrifield):
    cache_key = "agrifield_{}_status".format(agrifield.id)
    cache.set(cache_key, "being processed", None)
    agrifield.execute_model()
    cache.set(cache_key, "done", None)


@app.task
def add_irrigations_from_telemetric_flowmeters():
    """
    A scheduled task that inserts `AppliedIrrigation` entries for all the
    flowmeters in the system. For the time being, it's only `LoRA_ARTAFlowmeter`
    """
    if settings.AIRA_THE_THINGS_NETWORK_ACCESS_KEY:
        _add_irrigations_for_LoRA_ARTA_flowmeters()


def _add_irrigations_for_LoRA_ARTA_flowmeters():
    data_points = _get_ttn_data()
    device_ids = {d["device_id"] for d in data_points}
    for device_id in device_ids:
        filtered_data_points = [d for d in data_points if d["device_id"] == device_id]
        try:
            flowmeter = LoRA_ARTAFlowmeter.objects.get(device_id=device_id)
            flowmeter.create_irrigations_in_bulk(filtered_data_points)
        except LoRA_ARTAFlowmeter.DoesNotExist:
            logger.warn(f"Got non-existing flowmeter with id={device_id} from TTN.")


def _get_ttn_data(since="1d"):
    headers = {"Authorization": f"key {settings.AIRA_THE_THINGS_NETWORK_ACCESS_KEY}"}
    url = f"{settings.AIRA_THE_THINGS_NETWORK_BASE_URL}?last={since}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return [
        {
            "sensor_frequency": d["SensorFrequency"],
            "timestamp": d["time"],
            "device_id": d["device_id"],
        }
        for d in response.json()
        if d["SensorFrequency"]
    ]
