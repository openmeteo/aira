# Aira: An Irrigation Advisor

[![Build Status][travis-button]][travis]
[![Coverage Status][codecov-button]][codecov]

[travis-button]: http://img.shields.io/travis/openmeteo/aira.svg
[travis]: https://travis-ci.org/openmeteo/aira
[codecov-button]: https://codecov.io/gh/openmeteo/aira/branch/master/graph/badge.svg
[codecov]: https://codecov.io/gh/openmeteo/aira

Aira is a web application that calculates soil water balance in order
to provide users with irrigation recommendation.

## Configuration

Aira supports all Django, django-registration-redux and Celery settings.
In addition, it supports these settings:

- **AIRA_DATA_HISTORICAL**, **AIRA_DATA_FORECAST**. Absolute paths to
  directories holding TIFF files with spatial meteorological data.
  "Historical" is measured data, whereas "forecast" refers to
  meteorological forecasts. The filename format is
  `daily_{variable}-{YYYY-MM-DD}.tif` where `{variable}` is one of
  `evaporation`, `humidity`, `humidity_max`, `humidity_min`, `rain`,
  `solar_radiation`, `temperature`, `temperature_max`, `temperature_min` and
  `wind_speed`. Only `evaporation` is actually used for calculations,
  and the rest are used for showing on the front page map (with the help
  of mapserver) and for extracting historical data for a point (i.e. an
  (agri)field).

- **AIRA_DATA_SOIL**. Absolute path to a directory holding TIFF files
  with data for the soil. See "Soil data" below.

- **AIRA_TIMESERIES_CACHE_DIR**. Absolute path to a directory where it
  caches point time series. When the historical data for an agrifield
  are requested, aira extracts them from the rasters in
  `AIRA_DATA_HISTORICAL`. Since this is a time-consuming operation, it
  caches the result in `AIRA_TIMESERIES_CACHE_DIR` in case they are
  re-requested.

- **AIRA_MAPSERVER_BASE_URL**. The raster maps for the front page are
  served by a geographical server such as mapserver or geoserver. This
  is the URL of the geographical server, such as
  `https://arta.interregir2ma.eu/mapserver/` or `/mapserver/`.

- **AIRA_DEMO_USER_INITIAL_AGRIFIELDS**. When running `python manage.py
  demo_user` on an empty installation, the demo user and some demo
  fields are created. This holds the initial agrifields to be created
  (see `aira_project/settings/base.py` for details).

- **AIRA_MAP_DEFAULT_CENTER**, **AIRA_MAP_DEFAULT_ZOOM**. The default
  center for the map as a (longitude, latitude) tuple of floats, and the
  default zoom, as an integer. This defines the initial centering and
  zooming of a map if there's no reason to do something else (e.g. if a
  map shows agrifields, it might center and zoom on the agrifields).

- **AIRA_CELERY_SEND_TASK_ERROR_EMAILS**. By default, this has the value
  `False`. If you set it to `True`, whenever a Celery task encounters an
  error (raises an uncaught exception), the admins will be emailed.

## Soil data

Part of the configuration is a set of GeoTIFF files with information
about the soil. These files are placed in the directory specified by
`AIRA_DATA_SOIL`. The files are these:

- **fc.tif**. The field capacity.
- **theta_s.tif**. Water content when saturated.
- **pwp.tif**. The permanent wilting point.
- **a_1d.tif** and **b.tif**. Parameters used when calculating
  draintime.
- **theta-YYYY-MM-DD.tif** (optional). The initial conditions for
  running the soil water model are normally that on the previous 15
  March the soil was at field capacity. However, if a
  `theta-YYYY-MM-DD.tif` file exists and the date specified in the file
  name is more recent than the previous 15 March, it is assumed instead
  that the water content at the date specified is what is specified by
  the file. The purpose of this feature is to enable the system to work
  in the first year it is installed at an area, when meteorological data
  might become available mid-season.

## License

© 2014-2020 TEI of Epirus and University of Ioannina

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or (at
your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.
