from pymongo import MongoClient, DESCENDING, ASCENDING
import streamlit as st
from datetime import datetime, timedelta, time as datetime_time
from gridfs import GridFS
import io
from bson import ObjectId
import pandas as pd
import math
from collections import Counter

time_min = datetime_time.min
time_max = datetime_time.max

def get_river_locations():
    client = None
    try:
        client = MongoClient(st.secrets["MONGODB_URI"])
        db = client[st.secrets["MONGODB_DATABASE"]]
        collection = db["River"]
        rivers_cursor = collection.find({}, {"_id": 1, "nama": 1, "latitude": 1, "longitude": 1}).sort("nama", ASCENDING)
        rivers_data = []
        for river in rivers_cursor:
            try:
                if 'latitude' in river and river['latitude'] and 'longitude' in river and river['longitude']:
                     river['latitude'] = float(river['latitude'])
                     river['longitude'] = float(river['longitude'])
                     rivers_data.append(river)
                else:
                    pass
            except (ValueError, TypeError) as conv_err:
                pass
        if client: client.close()
        return rivers_data
    except Exception as e:
        print(f"Error mongo get_river_locations: {e}")
        if client: client.close()
        return []


def get_mongo_data(start_date=None, end_date=None, limit=None, sort_order=ASCENDING, sungai_id=None):
    client = None
    try:
        client = MongoClient(st.secrets["MONGODB_URI"])
        db = client[st.secrets["MONGODB_DATABASE"]]
        collection = db[st.secrets["MONGODB_COLLECTION"]]

        query = {}
        if sungai_id:
            try:
                query["sungai_id"] = ObjectId(sungai_id)
            except Exception:
                 print(f"Error mongo: Invalid ObjectId format for sungai_id {sungai_id}")
                 if client: client.close()
                 return []

        time_query = {}
        if start_date and end_date:
            start_dt = datetime.combine(start_date, time_min)
            end_dt = datetime.combine(end_date, time_max)
            time_query = {"timestamp": {"$gte": start_dt, "$lte": end_dt}}
        elif not limit:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=1)
            time_query = {"timestamp": {"$gte": start_dt, "$lte": end_dt}}

        if time_query:
             query.update(time_query)


        cursor = collection.find(query).sort("timestamp", sort_order)

        if limit:
            cursor = cursor.limit(limit)

        data = list(cursor)
        if client: client.close()
        return data
    except Exception as e:
        print(f"Error mongo get_mongo_data: {e}")
        if client: client.close()
        return []


def get_mongo_data_for_chat(start_date=None, end_date=None):
    client = None
    try:
        client = MongoClient(st.secrets["MONGODB_URI"])
        db = client[st.secrets["MONGODB_DATABASE"]]
        collection = db[st.secrets["MONGODB_COLLECTION"]]

        query = {}
        if start_date and end_date:
            start_dt = datetime.combine(start_date, time_min)
            end_dt = datetime.combine(end_date, time_max)
            query = {"timestamp": {"$gte": start_dt, "$lte": end_dt}}


        data = list(collection.find(query).sort("timestamp", 1))
        if client: client.close()
        return data
    except Exception as e:
        print(f"Error mongo get_mongo_data_for_chat: {e}")
        if client: client.close()
        return []

def save_report(report_data):
    client = None
    try:
        client = MongoClient(st.secrets["MONGODB_URI"])
        db = client[st.secrets["MONGODB_DATABASE"]]
        collection = db["Report"]
        insert_result = collection.insert_one(report_data)
        if client: client.close()
        return insert_result.inserted_id if insert_result.acknowledged else None
    except Exception as e:
        print(f"Error mongo save_report: {e}")
        if client: client.close()
        return None

def save_report_with_photo_gridfs(report_metadata, photo_data, photo_filename, photo_content_type):
    client = None
    photo_id = None
    try:
        client = MongoClient(st.secrets["MONGODB_URI"])
        db = client[st.secrets["MONGODB_DATABASE"]]
        fs = GridFS(db)

        photo_id = fs.put(
            io.BytesIO(photo_data),
            filename=photo_filename,
            contentType=photo_content_type
        )

        report_metadata['foto_gridfs_id'] = photo_id
        report_metadata['nama_foto'] = photo_filename
        report_metadata['tipe_konten_foto'] = photo_content_type

        collection = db["Report"]
        insert_result = collection.insert_one(report_metadata)

        if client: client.close()
        return insert_result.inserted_id if insert_result.acknowledged else None
    except Exception as e:
        print(f"Error mongo save_report_with_photo_gridfs: {e}")
        if photo_id and client:
            try:
                db = client[st.secrets["MONGODB_DATABASE"]]
                fs = GridFS(db)
                fs.delete(photo_id)
            except Exception as del_e:
                 print(f"Error mongo deleting orphan GridFS file {photo_id}: {del_e}")
        if client: client.close()
        return None

def _process_single_river_summary(db, monitoring_collection_name, river_id, river_name, days_history):
    monitoring_collection = db[monitoring_collection_name]
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days_history)
    query = {"sungai_id": river_id, "timestamp": {"$gte": start_dt, "$lte": end_dt}}
    monitoring_data = list(monitoring_collection.find(query).sort("timestamp", DESCENDING))

    if not monitoring_data:
        return "Tidak ada data sensor.", None

    df = pd.DataFrame(monitoring_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    numeric_cols = ['delta_per_min', 'temperature', 'humidity', 'raindrop_percent', 'distance']
    for col in numeric_cols:
         if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
         else: df[col] = pd.NA

    latest_reading = df.iloc[0]
    latest_ts_str = latest_reading.name.strftime('%d %B %Y, %H:%M')

    summary = f"Data sensor terakhir pada {latest_ts_str}:\n"

    latest_rate = latest_reading.get('delta_per_min')
    latest_temp = latest_reading.get('temperature')
    latest_hum = latest_reading.get('humidity')
    latest_rain = latest_reading.get('raindrop_percent')
    latest_status = latest_reading.get('status', 'N/A')

    summary += f"*   Status Sensor: **{latest_status}**\n"
    if pd.notna(latest_rate): summary += f"*   Laju Perubahan Air: {latest_rate:.2f} cm/min\n"
    if pd.notna(latest_temp): summary += f"*   Suhu: {latest_temp:.1f}°C\n"
    if pd.notna(latest_hum): summary += f"*   Kelembaban: {latest_hum:.1f}%\n"
    if pd.notna(latest_rain): summary += f"*   Kondisi Hujan Terakhir: {'Hujan' if latest_rain > 500 else 'Tidak Hujan'}\n"

    summary += f"\nRingkasan Sensor {days_history} Hari Terakhir:\n"
    avg_rate = df['delta_per_min'].mean()
    max_rate = df['delta_per_min'].max()
    min_rate = df['delta_per_min'].min()
    avg_temp = df['temperature'].mean()
    avg_hum = df['humidity'].mean()
    danger_periods = df[df['danger_banjir'] == True].shape[0]

    if pd.notna(avg_rate): summary += f"*   Rata-rata Laju Perubahan: {avg_rate:.2f} cm/min\n"
    if pd.notna(max_rate): summary += f"*   Laju Kenaikan Tertinggi: {max_rate:.2f} cm/min\n"
    if pd.notna(min_rate): summary += f"*   Laju Penurunan Terendah: {min_rate:.2f} cm/min\n"
    if pd.notna(avg_temp): summary += f"*   Rata-rata Suhu: {avg_temp:.1f}°C\n"
    if pd.notna(avg_hum): summary += f"*   Rata-rata Kelembaban: {avg_hum:.1f}%\n"
    if danger_periods > 0: summary += f"*   Peringatan Bahaya Banjir dari Sensor: {danger_periods} kali\n"
    rainy_periods_count = df[df['raindrop_percent'] > 500].shape[0]
    if rainy_periods_count > 0:
        summary += f"*   Sensor mendeteksi adanya periode hujan.\n"
    else:
         summary += f"*   Sensor tidak mendeteksi adanya periode hujan.\n"

    return summary, latest_status

def _process_single_river_reports(db, report_collection_name, river_id, river_name, days_history):
    report_collection = db[report_collection_name]
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days_history)
    query = {"sungai_id": river_id, "timestamp": {"$gte": start_dt, "$lte": end_dt}}
    reports_data = list(report_collection.find(query).sort("timestamp", DESCENDING))

    if not reports_data:
        return "Tidak ada laporan warga.", None

    latest_report = reports_data[0]
    latest_report_ts_str = latest_report['timestamp'].strftime('%d %B %Y, %H:%M')
    latest_reported_conditions = ", ".join(latest_report.get('kondisi_terpilih', []))
    latest_reported_trash = latest_report.get('jumlah_sampah', 'N/A')

    summary = f"Laporan warga terakhir pada {latest_report_ts_str}:\n"
    summary += f"*   Kondisi Dilaporkan: **{latest_reported_conditions}**\n"
    summary += f"*   Jumlah Sampah: {latest_reported_trash}\n"
    if latest_report.get('deskripsi'):
        summary += f"*   Deskripsi: {latest_report['deskripsi'][:100]}...\n"

    summary += f"\nRingkasan Laporan Warga {days_history} Hari Terakhir:\n"
    report_count = len(reports_data)
    summary += f"*   Jumlah Laporan Diterima: {report_count}\n"

    all_conditions = [cond for report in reports_data for cond in report.get('kondisi_terpilih', [])]
    if all_conditions:
         condition_counts = Counter(all_conditions)
         common_conditions = ", ".join([f"{cond}({count}x)" for cond, count in condition_counts.most_common(3)])
         summary += f"*   Kondisi Paling Sering Dilaporkan: {common_conditions}\n"

    all_trash_levels = [report.get('jumlah_sampah') for report in reports_data if report.get('jumlah_sampah')]
    if all_trash_levels:
        trash_counts = Counter(all_trash_levels)
        common_trash = ", ".join([f"{level}({count}x)" for level, count in trash_counts.most_common(2)])
        summary += f"*   Jumlah Sampah Paling Sering Dilaporkan: {common_trash}\n"


    return summary, latest_reported_conditions

def get_all_river_summaries(days_history=7):
    client = None
    combined_summary = ""
    all_data_available = True
    try:
        client = MongoClient(st.secrets["MONGODB_URI"])
        db = client[st.secrets["MONGODB_DATABASE"]]
        monitoring_collection_name = st.secrets["MONGODB_COLLECTION"]
        report_collection_name = "Report"

        rivers = get_river_locations()

        if not rivers:
             return "Tidak ada data lokasi sungai yang ditemukan.", False

        for river in rivers:
            river_id = river.get('_id')
            river_name = river.get('nama', 'Sungai Tidak Dikenal')
            combined_summary += f"### Ringkasan untuk {river_name}\n"
            if river_id:
                sensor_summary, sensor_status = _process_single_river_summary(db, monitoring_collection_name, river_id, river_name, days_history)
                report_summary, report_conditions = _process_single_river_reports(db, report_collection_name, river_id, river_name, days_history)

                combined_summary += "**Data Sensor:**\n" + sensor_summary + "\n\n"
                combined_summary += "**Laporan Warga:**\n" + report_summary + "\n"

                if "Tidak ada data sensor" in sensor_summary or "Tidak ada laporan warga" in report_summary:
                     all_data_available = False

            else:
                 combined_summary += "Tidak dapat memproses data (ID tidak valid).\n"
                 all_data_available = False
            combined_summary += "\n---\n\n"

        if client: client.close()
        combined_summary += "\nCatatan: Ringkasan ini dibuat berdasarkan data sensor dan laporan warga yang tersedia dalam periode waktu tersebut."
        return combined_summary.strip(), all_data_available

    except Exception as e:
        print(f"Error mongo get_all_river_summaries: {e}")
        if client: client.close()
        return f"Terjadi kesalahan saat memproses data: {e}", False