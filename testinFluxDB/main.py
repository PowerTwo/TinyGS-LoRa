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

def CheckNameSat(nameSat):
    if nameSat == "Tianqi-7" or nameSat == "Tianqi-19" or nameSat == "Tianqi-22" or nameSat == "Tianqi-23" or nameSat == "Tianqi-21" \
            or nameSat == "Tianqi-24" or nameSat == "Tianqi-25" or nameSat == "Tianqi-26" or nameSat == "Tianqi-27" or nameSat == "Tianqi-28":
        return 0
    elif nameSat == "Norby-2":
        return 1
    elif nameSat == "RS52SD" or nameSat == "RS52SE":
        return 2
    else:
        return 3

client = InfluxDBClient(host='localhost', port=8086)
client.create_database('pyexample')
client.get_list_database()
client.switch_database('pyexample')

predictTimeParams = client.query('select * from predictTime')

checkAvailableData= list(predictTimeParams.get_points())

if checkAvailableData:
    count = checkAvailableData[0]['AOS']
    print("Có dữ liệu trong InfluxDB.")
    # Lấy điểm dữ liệu đầu tiên
    first_point_AOS = next(predictTimeParams.get_points())
    first_point_DUR = next(predictTimeParams.get_points())
    # Trích xuất giá trị của trường "AOS"
    checkAvailableAOS = first_point_AOS['AOS']
    checkAvailableDUR = first_point_DUR['DUR']-30
else:
    print("Không có dữ liệu trong InfluxDB.")
    checkAvailableAOS = 0
    checkAvailableDUR = 0

print(checkAvailableAOS)
print(checkAvailableDUR)
print(dt.datetime.now().timestamp())
print(checkAvailableAOS + checkAvailableDUR - dt.datetime.now().timestamp())

if (checkAvailableAOS + checkAvailableDUR) < dt.datetime.now().timestamp():
    HCM = Location(
        "HCM", latitude_deg=10.869, longitude_deg=106.803, elevation_m=10)

    satellites_getTLE = ['Tianqi-7','Tianqi-19','Tianqi-22','Tianqi-23','Tianqi-21','Tianqi-24','Norbi','Norby-2',
                         'Tianqi-25','Tianqi-26','Tianqi-27','Tianqi-28']

    # URL của tệp tin dữ liệu
    url = "https://api.tinygs.com/v1/tinygs_supported.txt"

    # Tải xuống tệp tin
    response = requests.get(url)


    # # Phân tách dữ liệu thành các dòng
    tle_data = response.text
    lines = tle_data.strip().split('\n')

    # Khởi tạo các mảng
    tle_line1 = []
    tle_line2 = []
    satellite_names = []

    # Duyệt qua từng dòng dữ liệu và lưu vào mảng tương ứng
    for i in range(0, len(lines), 3):
        satellite_name = lines[i].strip()
        satellite_names.append(satellite_name)
        tle_line1.append(lines[i + 1].strip())
        tle_line2.append(lines[i + 2].strip())

    data_pandas = []

    for satellite_getTLE in satellites_getTLE:
        if satellite_getTLE in satellite_names:
            position = satellite_names.index(satellite_getTLE)
            SATE_ID = satellite_names[position]
            SATE_TLE_LINES = (
                tle_line1[position],
                tle_line2[position])

            db = MemoryTLESource()
            db.add_tle(SATE_ID, SATE_TLE_LINES, dt.datetime.utcnow())
            predictor = TLEPredictor(SATE_ID, db)

            date = dt.datetime.utcnow()
            pass_ = predictor.get_next_pass(HCM, date, max_elevation_gt=10)
            data_pandas.append({
                'SatID': pass_.sate_id,
                'AOS': pass_.aos,
                # 25200 offset in seconds GMT+7
                'AOS UnixTime': int(pass_.aos.timestamp())+25200,
                'DUR': int(pass_.duration_s),
                'Max Elevation': int(pass_.max_elevation_deg),
                'TypeSat': CheckNameSat(pass_.sate_id),
                'TLE line1': tle_line1[position],
                'TLE line2': tle_line2[position]
            })
            for i in range(4):
                pass_ = predictor.get_next_pass(HCM, pass_.los, max_elevation_gt=10)
                data_pandas.append({
                    'SatID': pass_.sate_id,
                    'AOS': pass_.aos,
                    # 25200 offset in seconds GMT+7
                    'AOS UnixTime': int(pass_.aos.timestamp())+25200,
                    'DUR': int(pass_.duration_s),
                    'Max Elevation': int(pass_.max_elevation_deg),
                    'TypeSat': CheckNameSat(pass_.sate_id),
                    'TLE line1': tle_line1[position],
                    'TLE line2': tle_line2[position]
                })

    # Tạo DataFrame từ danh sách dữ liệu
    df = pd.DataFrame(data_pandas)
    # print(df)

    # Sắp xếp DataFrame theo thứ tự tăng dần của biến max_elevation
    df_sorted = df.sort_values(by='AOS UnixTime')
    print(df_sorted)

    result = client.query('delete from predictTime')

    for i in range(df_sorted.shape[0]):
        satID = df_sorted.loc[i,"SatID"]
        aos = df_sorted.loc[i,"AOS UnixTime"]
        dur = df_sorted.loc[i,"DUR"]
        typeSat = df_sorted.loc[i,"TypeSat"]
        tle_line1 = df_sorted.loc[i, "TLE line1"]
        tle_line2 = df_sorted.loc[i, "TLE line2"]
        json_body = [
            {
                "measurement": "predictTime",
                "tags": {
                    "SatID": satID,
                },
                "time": aos,
                "fields": {
                    "AOS": aos,
                    "DUR": dur,
                    "TypeSat": typeSat,
                    "TLEline1": tle_line1,
                    "TLEline2": tle_line2
                }
            }
        ]
        print(json_body)
        client.write_points(json_body)

    result = client.query('select * from predictTime')
    print(result)
    
