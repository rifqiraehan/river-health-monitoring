# File: pages/dashboard.py
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from utils import get_mongo_data

def main():
    st.title("Dashboard Kesehatan Sungai")

    # Filter tanggal di sidebar
    st.sidebar.header("Pengaturan")
    use_date_range = st.sidebar.toggle("Filter Rentang Tanggal", value=False)

    # Rentang tanggal default (7 hari terakhir) jika tidak ada filter
    default_start_date = datetime.now() - timedelta(days=7)
    default_end_date = datetime.now()

    if use_date_range:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Tanggal Mulai", default_start_date)
        with col2:
            end_date = st.date_input("Tanggal Selesai", default_end_date)
    else:
        start_date, end_date = default_start_date, default_end_date

    # Ambil data dari MongoDB berdasarkan rentang tanggal
    mongo_data = get_mongo_data(start_date, end_date)

    # Cek ketersediaan data
    if not mongo_data:
        st.warning("Data tidak tersedia.")
        return

    # Tampilkan data terbaru
    latest_data = mongo_data[-1]
    st.subheader("Data Terkini")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Ketinggian Air (cm)", f"{latest_data['distance']:.2f}")
    with col2:
        rain_status = "Hujan" if latest_data["raindrop"] == 1 else "Tidak Hujan"
        st.metric("Status Hujan", rain_status)
    with col3:
        st.metric("Suhu (°C)", f"{latest_data['temperature']:.2f}")
    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("Kelembaban (%)", f"{latest_data['humidity']:.2f}")
    with col5:
        st.metric("Peringatan", latest_data["warning"])
    with col6:
        st.write("")

    # Tampilkan grafik jika ada cukup data
    st.subheader("Grafik Data Sensor")
    if len(mongo_data) > 1:
        df = pd.DataFrame(mongo_data)

        if '_id' in df.columns:
            df = df.drop(columns=['_id'])
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Grafik suhu
        temp_chart = alt.Chart(df).mark_line(color='red').encode(
            x='timestamp:T',
            y=alt.Y('temperature:Q', title='Suhu (°C)', scale=alt.Scale(domain=[min(df['temperature'])-5, max(df['temperature'])+5])),
            tooltip=['timestamp', 'temperature']
        ).properties(width=700, height=300)

        # Grafik kelembaban
        hum_chart = alt.Chart(df).mark_line(color='blue').encode(
            x='timestamp:T',
            y=alt.Y('humidity:Q', title='Kelembaban (%)', scale=alt.Scale(domain=[min(df['humidity'])-10, max(df['humidity'])+10])),
            tooltip=['timestamp', 'humidity']
        ).properties(width=700, height=300)

        # Grafik ketinggian air
        distance_chart = alt.Chart(df).mark_line(color='green').encode(
            x='timestamp:T',
            y=alt.Y('distance:Q', title='Ketinggian Air (cm)', scale=alt.Scale(domain=[min(df['distance'])-5, max(df['distance'])+5])),
            tooltip=['timestamp', 'distance']
        ).properties(width=700, height=300)

        # Gabungkan grafik
        combined_chart = alt.layer(temp_chart, hum_chart).resolve_scale(y='independent')
        st.altair_chart(combined_chart, use_container_width=True)

        # Tampilkan grafik ketinggian air secara terpisah
        st.altair_chart(distance_chart, use_container_width=True)
    else:
        st.info("Tidak ada data yang cukup untuk grafik. Pilih rentang tanggal yang lebih luas.")

if __name__ == "__main__":
    main()