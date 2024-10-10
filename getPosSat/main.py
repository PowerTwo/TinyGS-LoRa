import datetime as dt
import unittest
import os
import pickle
import tempfile
from unittest.mock import patch
import requests
import json
import datetime
import pandas as pd
from influxdb import InfluxDBClient

from orbit_predictor.sources import get_predictor_from_tle_lines
from orbit_predictor.coordinate_systems import ecef_to_llh
from orbit_predictor.coordinate_systems import llh_to_ecef
from orbit_predictor.locations import Location, ARG
from orbit_predictor.predictors import (
    NotReachable,
    Position,
    PredictedPass,
    TLEPredictor,
)
from orbit_predictor.predictors.base import ONE_SECOND
from orbit_predictor.sources import MemoryTLESource

client = InfluxDBClient(host='localhost', port=8086)
# client.create_database('pyexample')
# client.get_list_database()
client.switch_database('pyexample')

# Thực hiện truy vấn để lấy dòng đầu tiên của TLEline1 và TLEline2
query = 'SELECT TLEline1, TLEline2 FROM predictTime LIMIT 1'
results = client.query(query)

# Lấy dòng đầu tiên
first_point = next(results.get_points())
TLEline1 = first_point["TLEline1"]
TLEline2 = first_point["TLEline2"]

# Tạo TLE_LINES
TLE_LINES = (
    TLEline1,
    TLEline2
)

# Gọi hàm predictor
predictor = get_predictor_from_tle_lines(TLE_LINES)

lat, lon, alt = ecef_to_llh(predictor.get_only_position(dt.datetime.utcnow()))
lat = round(lat, 3)
lon = round(lon, 3)
alt = round(alt, 3)

client.switch_database('map_ttgo_dev3')
json_body = [
    {
        "measurement": "map_ttgo_dev3",
        "tags": {
            "Map": "dot",
        },
        "time": dt.datetime.utcnow(),
        "fields": {
            "longitude": lon,
            "latitude": lat,
            "altitude": alt,
        }
    }
]
print(json_body)
client.write_points(json_body)