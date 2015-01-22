import os
from datetime import datetime, timedelta
import glob
from django.conf import settings
from django.utils import timezone

from osgeo import gdal, ogr, osr
from pthelma.spatial import (extract_point_from_raster,
                             extract_point_timeseries_from_rasters)
from pthelma.swb import SoilWaterBalance

from aira.models import Agrifield

# GEO_DATA_CONFIG
PRECIP_FILES = glob.glob(os.path.join(settings.AIRA_DATA_FILE_DIR,
                                      'daily_rain*.tif'))
EVAP_FILES = glob.glob(os.path.join(settings.AIRA_DATA_FILE_DIR,
                                    'daily_evaporation*.tif'))
FC_FILE = os.path.join(settings.AIRA_COEFFS_FILE_DIR,
                       'fc.tif')
PWP_FILE = os.path.join(settings.AIRA_COEFFS_FILE_DIR,
                        'pwp.tif')


def rasters2point(lat, long, files):
    point = ogr.Geometry(ogr.wkbPoint)
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(4326)
    point.AssignSpatialReference(sr)
    point.AddPoint(long, lat)
    return extract_point_timeseries_from_rasters(files, point)


def raster2point(lat, long, file):
    point = ogr.Geometry(ogr.wkbPoint)
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(4326)
    point.AssignSpatialReference(sr)
    point.AddPoint(long, lat)
    f = gdal.Open(file)
    return extract_point_from_raster(point, f)


def make_tz_datetime(date):
    # Convert datetime.date object to datetime
    # Also make sure datetime time object has
    # settings.base.USE_TZ
    tz_config = timezone.get_default_timezone()
    return datetime(date.year, date.month, date.day).replace(tzinfo=tz_config)


def swb_finish_date(precipitation, evapotranspiration):
    plast = precipitation.bounding_dates()[1]
    elast = evapotranspiration.bounding_dates()[1]
    return min(plast, elast)


def irrigation_amount_view(agrifield_id):
    try:
        # Select Agrifield
        f = Agrifield.objects.get(pk=agrifield_id)
        # Create Point Meteo Timeseries
        precip = rasters2point(f.latitude, f.longitude, PRECIP_FILES)
        evap = rasters2point(f.latitude, f.longitude, EVAP_FILES)
        fc = raster2point(f.latitude, f.longitude, FC_FILE)
        wp = raster2point(f.latitude, f.longitude, PWP_FILE)
        rd = float(f.ct.ct_rd)
        kc = float(f.ct.ct_kc)
        irr_eff = float(f.irrt.irrt_eff)
        # Initial Soil moisture is constant
        initial_sm = fc
        p = float(f.ct.ct_coeff)
        rd_factor = 1
        # Time period
        start_date = f.irrigationlog_set.latest().time
        start_date = make_tz_datetime(start_date)
        # Warning user that last irrigation log is more than 5 days old
        now = timezone.now()
        warning = False
        warning_days = None
        if now - start_date >= timedelta(days=5):
            warning = True
            warning_days = (now - start_date).days
        # Depends on the latest AIRA_DATA_FILE
        finish_date = make_tz_datetime(swb_finish_date(precip, evap))
        # pthelma.swb
        s = SoilWaterBalance(fc, wp, rd, kc, p,
                             precip, evap,
                             irr_eff, rd_factor)
        next_irr = s.irrigation_water_amount(start_date, initial_sm, finish_date)
        next = {'s': s, 'next_irr': str(round(next_irr, 2)),
                'warning': warning, 'warning_days': warning_days}
    except:
        next = {'s': None, 'next_irr': None, 'warning': warning,
                'warning_days': warning_days}
    return next
