from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext as _


def map(request):
    query_element = ""
    thunderforest_api_key = getattr(settings, "AIRA_THUNDERFOREST_API_KEY", None)
    if thunderforest_api_key:
        query_element = f"apikey={thunderforest_api_key}"
    lang = translation.get_language() or "en"
    map_default_center = ",".join([str(x) for x in settings.AIRA_MAP_DEFAULT_CENTER])
    map_js = f"""
        aira.thunderforestApiKeyQueryElement = "{query_element}";
        aira.mapserverBaseUrl = "{settings.AIRA_MAPSERVER_BASE_URL}{lang}/";
        aira.mapDefaultCenter = [{map_default_center}];
        aira.mapDefaultZoom = {settings.AIRA_MAP_DEFAULT_ZOOM};
        aira.strings = {{ covered_area: "{_("Covered area")}" }};
        """
    return {
        "map_js": map_js,
        "google_maps_api_key": getattr(settings, "AIRA_GOOGLE_MAPS_API_KEY", ""),
    }
