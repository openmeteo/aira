import datetime as dt
import os
from glob import glob

from django.conf import settings
from django.core.cache import cache

import iso8601
import numpy as np
import pandas as pd
import pytz
from hspatial import PointTimeseries, extract_point_from_raster
from osgeo import gdal
from swb import (
    calculate_crop_evapotranspiration,
    calculate_soil_water,
    get_effective_precipitation,
)


class AgrifieldSWBMixin:
    """Functionality about running the SWB model for an Agrifield.

    This class is to be mixed in models.Agrifield; it contains the part of the
    functionality that has to do with running the swb model on the Agrifield.
    """

    @property
    def root_depth(self):
        return (float(self.root_depth_min) + float(self.root_depth_max)) / 2

    @property
    def draintime(self):
        raster_a = os.path.join(settings.AIRA_DATA_SOIL, "a_1d.tif")
        a = extract_point_from_raster(self.location, gdal.Open(raster_a))
        raster_b = os.path.join(settings.AIRA_DATA_SOIL, "b.tif")
        b = extract_point_from_raster(self.location, gdal.Open(raster_b))
        return round(a * self.root_depth ** b)

    def _point_timeseries(self, category, varname):
        return PointTimeseries(
            self.location,
            prefix=os.path.join(
                getattr(settings, "AIRA_DATA_" + category), "daily_" + varname
            ),
            start_date=InitialConditions(self).date,
            default_time=dt.time(23, 59),
        ).get()

    def _get_timeseries_from_rasters(self, var):
        historical = self._point_timeseries("HISTORICAL", var)
        forecast = self._point_timeseries("FORECAST", var)
        self.historical_end_date = historical.data.index[-1]
        forecast_start_date = self.historical_end_date + dt.timedelta(minutes=1)
        forecast.data = forecast.data[forecast_start_date:]
        self.forecast_start_date = forecast.data.index[0]
        return pd.concat((historical.data["value"], forecast.data["value"]))

    def _determine_effective_precipitation(self):
        self.timeseries["precipitation"] = self._get_timeseries_from_rasters("rain")
        get_effective_precipitation(self.timeseries)

    def _determine_evaporation(self):
        self.timeseries["ref_evapotranspiration"] = self._get_timeseries_from_rasters(
            "evaporation"
        )

    def _determine_irrigation(self):
        self.timeseries["applied_irrigation"] = 0  # Zero is the default
        self.timeseries["applied_irrigation"] = self.timeseries[
            "applied_irrigation"
        ].astype("object")
        self.timeseries["actual_net_irrigation"] = 0  # Zero is the default
        self.timeseries["actual_net_irrigation"] = self.timeseries[
            "actual_net_irrigation"
        ].astype("object")
        tz = pytz.timezone(settings.TIME_ZONE)
        start = tz.localize(
            self.timeseries.index[0] - dt.timedelta(hours=23, minutes=59)
        )
        end = tz.localize(self.timeseries.index[-1])
        applied_irrigations = self.appliedirrigation_set.filter(
            timestamp__range=(start, end)
        )
        for applied_irrigation in applied_irrigations:
            date = dt.datetime.combine(
                applied_irrigation.timestamp.date(), dt.time(23, 59)
            )
            volume = applied_irrigation.volume
            if volume is None:
                # When an irrigation event has been logged but we don't know how
                # much, we assume we reached field capacity. At that point we use
                # "True" instead of a number, which signals to
                # swb.calculate_soil_water() to assume we irrigated with the recommended
                # amount.
                self.timeseries.at[date, "actual_net_irrigation"] = True
                self.timeseries.at[date, "applied_irrigation"] = None
            else:
                applied_water_mm = float(volume / self.area * 1000)
                self.timeseries.at[date, "actual_net_irrigation"] = (
                    applied_water_mm * self.irrigation_efficiency
                )
                self.timeseries.at[date, "applied_irrigation"] = applied_water_mm

    def _determine_crop_evapotranspiration(self):
        calculate_crop_evapotranspiration(
            timeseries=self.timeseries,
            planting_date=self.crop_type.most_recent_planting_date,
            kc_offseason=self.crop_type.kc_offseason,
            kc_initial=self.crop_type.kc_initial,
            kc_stages=self.crop_type.kc_stages,
        )

    def prepare_timeseries(self):
        """Setup self.timeseries, a DataFrame with the data needed to run the model."""
        self.timeseries = pd.DataFrame()
        self._determine_evaporation()
        self._determine_effective_precipitation()
        self.timeseries.dropna()
        self._determine_crop_evapotranspiration()
        self._determine_irrigation()

    def run_swb_model(self):
        return calculate_soil_water(
            timeseries=self.timeseries,
            theta_s=float(self.theta_s),
            theta_fc=self.field_capacity,
            theta_wp=self.wilting_point,
            zr=self.root_depth,
            zr_factor=1000,
            p=float(self.p),
            draintime=self.draintime,
            theta_init=InitialConditions(self).theta,
            mif=self.irrigation_optimizer,
        )

    def run_swb_model_normally(self):
        d = self.run_swb_model()
        self.raw = d["raw"]
        self.taw = d["taw"]
        self.timeseries["recommendation"] = self.timeseries["dr"] > self.raw
        self.timeseries["ifinal"] = (
            self.timeseries["recommended_net_irrigation"] / self.irrigation_efficiency
        )
        self.timeseries["ifinal_m3"] = self.timeseries["ifinal"] / 1000 * self.area

    def _extract_columns_from_timeseries(self, *cols):
        result = {}
        for col in cols:
            result[col] = self.timeseries[col].copy()
        return result

    def _import_columns_to_timeseries(self, saved_columns):
        for col, value in saved_columns.items():
            self.timeseries[col] = value

    def _rename_result_columns_in_timeseries(self, suffix):
        self.timeseries.rename(
            columns={
                "dr": "dr" + suffix,
                "theta": "theta" + suffix,
                "ks": "ks" + suffix,
                "recommended_net_irrigation": "recommended_net_irrigation" + suffix,
            },
            inplace=True,
        )

    def run_swb_model_for_performance_chart(self):
        saved_columns = self._extract_columns_from_timeseries(
            "actual_net_irrigation", "dr", "theta", "ks", "recommended_net_irrigation"
        )

        # We want the model to run ignoring the actual net irrigation, and instead
        # assume that the actual irrigation equals recommended irrigation.
        self.timeseries["actual_net_irrigation"] = True

        self.run_swb_model()
        self._rename_result_columns_in_timeseries(suffix="_theoretical")
        self._import_columns_to_timeseries(saved_columns)
        self.timeseries["ifinal_theoretical"] = self.timeseries.apply(
            lambda x: (
                x.recommended_net_irrigation_theoretical / self.irrigation_efficiency
            ),
            axis=1,
        )
        filter = self.timeseries["applied_irrigation"].isnull()
        self.timeseries.loc[filter, "applied_irrigation"] = self.timeseries.loc[
            filter, "ifinal_theoretical"
        ]

    def execute_model(self):
        if not self.in_covered_area:
            return
        self.prepare_timeseries()
        self.run_swb_model_normally()
        self.run_swb_model_for_performance_chart()
        result = {
            "raw": self.raw,
            "taw": self.taw,
            "timeseries": self.timeseries,
            "historical_end_date": self.historical_end_date,
            "forecast_start_date": self.forecast_start_date,
        }
        cache.set("model_run_{}".format(self.id), result, None)
        return result


class AgrifieldSWBResultsMixin:
    """Mostly properties related to accessing SWB model run results.

    This class is to be mixed in models.Agrifield; it contains mostly properties
    accessing the results of the SWB model run. They are mostly useful in templates.
    """

    @property
    def results(self):
        if self.in_covered_area:
            return cache.get("model_run_{}".format(self.id))
        else:
            return None

    @property
    def needs_irrigation(self):
        if not self.results:
            return None
        forecast_start_date = self.results["forecast_start_date"]
        return self.results["timeseries"]["ifinal"][forecast_start_date:].sum() > 0

    @property
    def alternative_irrigations(self):
        forecast_start_date = self.results["forecast_start_date"]
        timeseries = self.results["timeseries"]
        return timeseries.loc[timeseries["ifinal"] > 0][forecast_start_date:]

    @property
    def forecast_data(self):
        forecast_start_date = self.results["forecast_start_date"]
        timeseries = self.results["timeseries"]
        if "theta" in timeseries:
            timeseries["theta_actual"] = np.minimum(timeseries["theta"], self.theta_s)
        return timeseries[forecast_start_date:]

    @property
    def last_irrigation_is_outdated(self):
        try:
            last_irrigation_date = self.last_irrigation.timestamp.date()
            start_date = self.results["timeseries"].index[0].date()
            end_date = self.results["timeseries"].index[-1].date()
            return last_irrigation_date < start_date or last_irrigation_date > end_date
        except (TypeError, AttributeError, IndexError):
            return True


class InitialConditions:
    """Helper class that determines initial conditions for swb.

    The initial conditions for running the soil water model are normally that on the
    previous 15 March the soil was at field capacity. However, if a
    `theta-YYYY-MM-DD.tif` file exists and the date specified in the file name is more
    recent than the previous 15 March, it is assumed instead that the water content at
    the date specified is what is specified by the file.

    This class is initialized with an agrifield and exposes properties "date" and
    "theta", which are the initial conditions according to the rules above.
    """

    def __init__(self, agrifield):
        self.agrifield = agrifield

    @property
    def date(self):
        itrd = self._get_initial_theta_raster_date()
        if itrd is not None and itrd > self._start_of_season:
            return itrd
        else:
            return self._start_of_season

    def _get_initial_theta_raster_date(self):
        try:
            datestring = self._initial_theta_raster_file[-14:-4]
            return iso8601.parse_date(datestring).replace(tzinfo=None)
        except (TypeError, iso8601.ParseError):
            return None

    @property
    def _start_of_season(self):
        today = dt.date.today()
        result = dt.datetime(today.year, 3, 15, 0, 0)
        if result > dt.datetime.now():
            result = dt.datetime(today.year - 1, 3, 15, 0, 0)
        return result

    @property
    def theta(self):
        itrd = self._get_initial_theta_raster_date()
        if itrd is not None and itrd > self._start_of_season:
            return self._get_theta_init_from_raster()
        else:
            return self.agrifield.field_capacity

    def _get_theta_init_from_raster(self):
        if not self.agrifield.in_covered_area:
            return None
        else:
            return extract_point_from_raster(
                self.agrifield.location, gdal.Open(self._initial_theta_raster_file)
            )

    @property
    def _initial_theta_raster_file(self):
        pathnames = glob(os.path.join(settings.AIRA_DATA_SOIL, "theta-????-??-??.tif"))
        result = None
        for pathname in pathnames:
            datestr = pathname[-14:-4]
            if self._is_valid_date(datestr) and (result is None or pathname > result):
                result = pathname
        return result

    def _is_valid_date(self, datestr):
        try:
            iso8601.parse_date(datestr)
            return True
        except iso8601.ParseError:
            return False
