from pymongo import MongoClient
import streamlit as st
from datetime import datetime

def get_mongo_data(start_date=None, end_date=None):
    """
    Mengambil data dari MongoDB berdasarkan rentang tanggal.
    Jika tidak ada rentang, ambil data terbaru.
    """
    try:
        client = MongoClient(st.secrets["MONGODB_URI"])
        db = client[st.secrets["MONGODB_DATABASE"]]
        collection = db[st.secrets["MONGODB_COLLECTION"]]

        if start_date and end_date:
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            query = {"timestamp": {"$gte": start_dt, "$lte": end_dt}}
            data = list(collection.find(query).sort("timestamp", 1))
        else:
            data = list(collection.find().sort("timestamp", -1).limit(1))

        client.close()
        return data
    except Exception as e:
        st.error(f"Error saat mengambil data dari MongoDB: {e}")
        return []

def get_mongo_data_for_chat(start_date=None, end_date=None):
    """
    Mengambil seluruh data dari MongoDB jika tidak ada filter tanggal.
    Jika ada rentang tanggal, ambil data dalam rentang itu.
    """
    try:
        client = MongoClient(st.secrets["MONGODB_URI"])
        db = client[st.secrets["MONGODB_DATABASE"]]
        collection = db[st.secrets["MONGODB_COLLECTION"]]

        if start_date and end_date:
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            query = {"timestamp": {"$gte": start_dt, "$lte": end_dt}}
        else:
            query = {}

        data = list(collection.find(query).sort("timestamp", 1))
        client.close()
        return data
    except Exception as e:
        st.error(f"Error saat mengambil data dari MongoDB: {e}")
        return []