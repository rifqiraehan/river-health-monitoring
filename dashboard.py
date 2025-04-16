import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from utils import get_mongo_data

def main():
    st.title("Dashboard Kesehatan Sungai")

    st.sidebar.header("Pengaturan")
    use_date_range = st.sidebar.toggle("Filter Rentang Tanggal", value=False)

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

    mongo_data = get_mongo_data(start_date, end_date)

    if not mongo_data:
        st.warning("Data pada rentang ini tidak tersedia.")
        return

    latest_data = mongo_data[-1]
    st.subheader("Data Terkini")

    last_updated = latest_data['timestamp']
    formatted_time = last_updated.strftime("%d %B %Y, %H:%M")
    st.caption(f"Data terakhir diperbarui pada **{formatted_time}**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Jarak sensor terhadap permukaan air (cm)", f"{latest_data['distance']:.2f}")
    with col2:
        rain_status = "Hujan" if latest_data["raindrop"] == 1 else "Tidak Hujan"
        st.metric("Status Hujan", rain_status)
    with col3:
        st.metric("Suhu (°C)", f"{latest_data['temperature']:.2f}")
    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("Kelembaban (%)", f"{latest_data['humidity']:.2f}")
    with col5:
        warning_status = "Tidak Banjir" if latest_data["warning"] == 1 else "Banjir"
        st.metric("Peringatan", warning_status)

    with col6:
        st.write("")

    st.subheader("Grafik Data Sensor")
    if len(mongo_data) > 1:
        df = pd.DataFrame(mongo_data)

        if '_id' in df.columns:
            df = df.drop(columns=['_id'])

        df['timestamp'] = pd.to_datetime(df['timestamp'])

        temp_chart = alt.Chart(df).mark_line(color='red').encode(
            x='timestamp:T',
            y=alt.Y('temperature:Q', title='Suhu (°C)', scale=alt.Scale(domain=[min(df['temperature'])-5, max(df['temperature'])+5])),
            tooltip=['timestamp', 'temperature']
        ).properties(width=700, height=300)

        hum_chart = alt.Chart(df).mark_line(color='blue').encode(
            x='timestamp:T',
            y=alt.Y('humidity:Q', title='Kelembaban (%)', scale=alt.Scale(domain=[min(df['humidity'])-10, max(df['humidity'])+10])),
            tooltip=['timestamp', 'humidity']
        ).properties(width=700, height=300)

        distance_chart = alt.Chart(df).mark_line(color='green').encode(
            x='timestamp:T',
            y=alt.Y('distance:Q', title='Ketinggian Air (cm)', scale=alt.Scale(domain=[min(df['distance'])-5, max(df['distance'])+5])),
            tooltip=['timestamp', 'distance']
        ).properties(width=700, height=300)

        combined_chart = alt.layer(temp_chart, hum_chart).resolve_scale(y='independent')
        st.altair_chart(combined_chart, use_container_width=True)

        st.altair_chart(distance_chart, use_container_width=True)
    else:
        st.info("Tidak ada data yang cukup untuk grafik. Pilih rentang tanggal yang lebih luas.")

if __name__ == "__main__":
    main()