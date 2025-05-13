import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, time as datetime_time
import time
from pymongo import DESCENDING, ASCENDING
from mongo_utils import get_mongo_data, get_river_locations
from bson import ObjectId

time_min = datetime_time.min
time_max = datetime_time.max
RATE_THRESHOLD_DANGER_RAIN = 2.0
RATE_THRESHOLD_DANGER_NO_RAIN = 5.0
RATE_THRESHOLD_STABLE = 0.0
RATE_THRESHOLD_FALLING = -1.0
TURBIDITY_CLEAR_THRESHOLD_V = 2.5

def main():
    st.sidebar.header("Pengaturan")

    river_locations = get_river_locations()

    if not river_locations:
        st.sidebar.error("Tidak dapat memuat daftar lokasi sungai.")
        st.stop()

    river_names = [river['nama'] for river in river_locations]
    river_map = {river['nama']: str(river['_id']) for river in river_locations}
    river_coords_map = {str(river['_id']): {'latitude': river.get('latitude'), 'longitude': river.get('longitude')}
                        for river in river_locations}

    default_river_name = "Sungai Keputih Tegal Timur"
    default_index = river_names.index(default_river_name) if default_river_name in river_names else 0
    selected_river_name = st.sidebar.selectbox(
        "Pilih Lokasi Sungai",
        options=river_names,
        index=default_index
    )

    selected_sungai_id = river_map.get(selected_river_name)
    selected_river_coords = river_coords_map.get(selected_sungai_id) if selected_sungai_id else None

    use_date_range = st.sidebar.toggle("Filter Rentang Tanggal", value=False)

    today_date = datetime.now().date()

    default_start_date = today_date - timedelta(days=7)
    default_end_date = today_date

    df_full = pd.DataFrame()
    df_graph_data = pd.DataFrame()
    resample_freq = '30min'
    graph_time_mode = '30 Menit (5 Jam Terakhir dari Data Terbaru)'
    fetch_start_datetime = None
    fetch_end_datetime = None
    data_valid = True

    latest_data_from_db = get_mongo_data(
        limit=1,
        sort_order=DESCENDING,
        sungai_id=selected_sungai_id
    )
    latest_data = latest_data_from_db[0] if latest_data_from_db else None
    if latest_data and 'timestamp' in latest_data:
        latest_data['timestamp'] = pd.to_datetime(latest_data['timestamp'], errors='coerce')

    if use_date_range:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date_selected = st.date_input("Tanggal Mulai", default_start_date)
        with col2:
            end_date_selected = st.date_input(
                "Tanggal Selesai",
                value=max(start_date_selected, default_end_date),
                min_value=start_date_selected
            )

        fetch_start_datetime = datetime.combine(start_date_selected, datetime_time.min)
        fetch_end_datetime = datetime.combine(end_date_selected, datetime_time.max)

        if fetch_start_datetime > fetch_end_datetime:
            st.sidebar.error("Tanggal Selesai tidak boleh sebelum Tanggal Mulai.")
            data_valid = False
        elif start_date_selected == end_date_selected:
            resample_freq = '15min'
            graph_time_mode = f'Per 15 Menit ({start_date_selected.strftime("%d %b %Y")})'
        else:
            resample_freq = 'D'
            graph_time_mode = 'Harian'
    else:
        if latest_data and not pd.isna(latest_data['timestamp']):
            latest_timestamp = latest_data['timestamp']
            fetch_end_datetime = latest_timestamp
            fetch_start_datetime = fetch_end_datetime - timedelta(hours=5)
            resample_freq = '15min'
            graph_time_mode = f'Per 15 Menit (5 Jam hingga {fetch_end_datetime.strftime("%d %b %Y, %H:%M")})'
        else:
            st.warning("Tidak ada data terbaru dalam database untuk grafik.")
            fetch_start_datetime = datetime.combine(today_date, datetime_time.min)
            fetch_end_datetime = datetime.combine(today_date, datetime_time.max)
            data_valid = False

    st.markdown("<h2>River Health Monitoring</h2>", unsafe_allow_html=True)
    st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
    .metric-card { padding: 1rem; border-radius: 0.5rem; color: white; display: flex; align-items: center; gap: 0.75rem; height: 100px; box-sizing: border-box; margin-bottom: 1rem; }
    .metric-card.loading { background-color: #e5e7eb; animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
    .metric-card.loading .metric-title, .metric-card.loading .metric-value, .metric-card.loading .metric-icon { visibility: hidden; }
    .bg-blue { background-color: #3b82f6; }
    .bg-green { background-color: #10b981; }
    .bg-red { background-color: #ef4444; }
    .bg-yellow { background-color: #f59e0b; }
    .bg-purple { background-color: #8b5cf6; }
    .bg-brown { background-color: #a16207; }
    .metric-title { font-size: 0.875rem; font-weight: 600; }
    .metric-value { font-size: 1.25rem; font-weight: 700; }
    .metric-icon { font-size: 1.5rem; }
    .text-content { display: flex; flex-direction: column; }
    .section-gap { margin-top: 1.5rem; }
    .stPlotlyChart { overflow-x: auto; }
    </style>
    """, unsafe_allow_html=True)

    subheader_text = f"Data Terkini di {selected_river_name}"
    st.subheader(subheader_text)
    timestamp_placeholder = st.empty()
    timestamp_placeholder.caption("Memuat data terkini...")

    col1, col2, col3 = st.columns(3)
    with col1: rate_placeholder = st.empty()
    with col2: rain_placeholder = st.empty()
    with col3: temp_placeholder = st.empty()

    col4, col5, col6 = st.columns(3)
    with col4: humidity_placeholder = st.empty()
    with col5: turbidity_placeholder = st.empty()
    with col6: status_placeholder = st.empty()

    metric_placeholders = [
        rate_placeholder, rain_placeholder, temp_placeholder,
        humidity_placeholder, turbidity_placeholder, status_placeholder
    ]

    for ph in metric_placeholders:
        ph.markdown(f"""<div class="metric-card loading"></div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

    graph_subheader_text = f"Grafik Rata-Rata {selected_river_name}"
    st.subheader(graph_subheader_text)

    rate_graph_placeholder = st.empty()
    temp_hum_graph_placeholder = st.empty()
    turbidity_graph_placeholder = st.empty()
    map_subheader_placeholder = st.empty()
    map_placeholder = st.empty()

    if latest_data and not pd.isna(latest_data['timestamp']):
        last_updated_time = latest_data['timestamp']
        formatted_time = last_updated_time.strftime("%d %B %Y, %H:%M:%S")
        timestamp_placeholder.caption(f"Data terakhir diperbarui di {selected_river_name} pada **{formatted_time}**")

        rate_val = latest_data.get('delta_per_min', None)
        rate_text = f"{rate_val:.2f}" if pd.notna(rate_val) else "N/A"
        rate_placeholder.markdown(f"""<div class="metric-card bg-blue"><i class="fas fa-tachometer-alt metric-icon"></i><div class="text-content"><div class="metric-title">Laju Perubahan (cm/min)</div><div class="metric-value">{rate_text}</div></div></div>""", unsafe_allow_html=True)

        rain_val = latest_data.get('raindrop_percent', 0)
        rain_status = "Hujan" if pd.notna(rain_val) and rain_val > 60 else "Tidak Hujan"
        rain_placeholder.markdown(f"""<div class="metric-card bg-green"><i class="fas fa-cloud-rain metric-icon"></i><div class="text-content"><div class="metric-title">Status Hujan</div><div class="metric-value">{rain_status}</div></div></div>""", unsafe_allow_html=True)

        temp_val = latest_data.get('temperature', None)
        temp_text = f"{temp_val:.1f}" if pd.notna(temp_val) else "N/A"
        temp_placeholder.markdown(f"""<div class="metric-card bg-red"><i class="fas fa-thermometer-half metric-icon"></i><div class="text-content"><div class="metric-title">Suhu (°C)</div><div class="metric-value">{temp_text}</div></div></div>""", unsafe_allow_html=True)

        hum_val = latest_data.get('humidity', None)
        hum_text = f"{hum_val:.1f}" if pd.notna(hum_val) else "N/A"
        humidity_placeholder.markdown(f"""<div class="metric-card bg-yellow"><i class="fas fa-tint metric-icon"></i><div class="text-content"><div class="metric-title">Kelembaban (%)</div><div class="metric-value">{hum_text}</div></div></div>""", unsafe_allow_html=True)

        turb_val = latest_data.get('turbidity_voltage', None)
        turb_text = f"{turb_val:.2f} V" if pd.notna(turb_val) else "N/A"
        turbidity_status = "Keruh" if pd.notna(turb_val) and turb_val > TURBIDITY_CLEAR_THRESHOLD_V else "Jernih"
        turbidity_placeholder.markdown(f"""<div class="metric-card bg-brown"><i class="fas fa-smog metric-icon"></i><div class="text-content"><div class="metric-title">Kekeruhan ({turbidity_status})</div><div class="metric-value">{turb_text}</div></div></div>""", unsafe_allow_html=True)

        status_text = latest_data.get('status', 'Tidak Diketahui') if pd.notna(latest_data.get('status')) else 'Tidak Diketahui'
        status_color = "bg-red" if "Bahaya" in status_text else "bg-purple"
        status_placeholder.markdown(f"""<div class="metric-card {status_color}"><i class="fas fa-info-circle metric-icon"></i><div class="text-content"><div class="metric-title">Status</div><div class="metric-value">{status_text}</div></div></div>""", unsafe_allow_html=True)
    else:
        timestamp_placeholder.caption("Tidak ada data terbaru.")
        for ph in metric_placeholders:
            ph.empty()
        st.warning("Tidak dapat memuat data terbaru untuk metrik.")

    if data_valid and fetch_start_datetime and fetch_end_datetime:
        with st.spinner("Memuat data grafik..."):
            mongo_data = get_mongo_data(
                start_date=fetch_start_datetime,
                end_date=fetch_end_datetime,
                sungai_id=selected_sungai_id,
                sort_order=ASCENDING
            )

            if not mongo_data:
                st.warning(f"Tidak ada data ditemukan untuk {selected_river_name} pada rentang waktu yang dipilih.")
                rate_graph_placeholder.empty()
                temp_hum_graph_placeholder.empty()
                turbidity_graph_placeholder.empty()
                df_full = pd.DataFrame()
                df_graph_data = pd.DataFrame()
            else:
                df_full = pd.DataFrame(mongo_data)

                if 'timestamp' in df_full.columns:
                    df_full['timestamp'] = pd.to_datetime(df_full['timestamp'], errors='coerce')
                    df_full.set_index('timestamp', inplace=True)
                    if df_full.index.isna().all():
                        st.error("Semua timestamp tidak valid.")
                        data_valid = False
                else:
                    st.error("Kolom 'timestamp' tidak ditemukan dalam data.")
                    data_valid = False

                if data_valid:
                    numeric_cols = ['delta_per_min', 'temperature', 'humidity', 'raindrop_percent', 'distance', 'turbidity_voltage']
                    for col in numeric_cols:
                        if col not in df_full.columns:
                            st.warning(f"Kolom '{col}' tidak ditemukan dalam data.")
                            df_full[col] = pd.NA
                        else:
                            df_full[col] = pd.to_numeric(df_full[col], errors='coerce')
                            if df_full[col].isnull().all():
                                st.warning(f"Kolom '{col}' hanya berisi nilai null.")

                    df_full.sort_index(inplace=True)

                    numeric_df = df_full.select_dtypes(include=['float64', 'int64'])

                    if not numeric_df.empty:
                        df_to_resample = numeric_df[
                            (numeric_df.index >= fetch_start_datetime) &
                            (numeric_df.index <= fetch_end_datetime)
                        ]

                        if not df_to_resample.empty:
                            df_to_resample = df_to_resample.infer_objects(copy=False)
                            df_to_resample = df_to_resample.interpolate(method='time', limit_direction='both')
                            df_graph_data = df_to_resample.resample(resample_freq).mean().dropna(how='all')
                        else:
                            df_graph_data = pd.DataFrame()
                            st.warning("Tidak ada data dalam rentang waktu yang dipilih untuk grafik.")
                    else:
                        df_graph_data = pd.DataFrame()
                        st.warning("Tidak ada kolom numerik yang valid untuk grafik.")
    else:
        df_full = pd.DataFrame()
        df_graph_data = pd.DataFrame()

    fig_rate_avg = go.Figure()
    if not df_graph_data.empty and 'delta_per_min' in df_graph_data.columns and not df_graph_data['delta_per_min'].isnull().all():
        fig_rate_avg.add_trace(go.Scatter(
            x=df_graph_data.index,
            y=df_graph_data['delta_per_min'],
            mode='lines+markers',
            name='Rata-Rata Laju Perubahan (cm/min)',
            line=dict(color='rgba(75, 0, 130, 0.9)', width=2)
        ))

        fig_rate_avg.add_hline(y=RATE_THRESHOLD_DANGER_NO_RAIN, line_dash="dash", line_color="red", annotation_text=f"Bahaya ({RATE_THRESHOLD_DANGER_NO_RAIN} cm/min)", annotation_position="top left", annotation_font_color="red")
        fig_rate_avg.add_hline(y=RATE_THRESHOLD_DANGER_RAIN, line_dash="dash", line_color="orange", annotation_text=f"Bahaya Hujan ({RATE_THRESHOLD_DANGER_RAIN} cm/min)", annotation_position="top right", annotation_font_color="orange")
        fig_rate_avg.add_hline(y=RATE_THRESHOLD_STABLE, line_dash="dot", line_color="grey", annotation_text="Stabil (0 cm/min)", annotation_position="bottom left", annotation_font_color="grey")
        fig_rate_avg.add_hline(y=RATE_THRESHOLD_FALLING, line_dash="dot", line_color="green", annotation_text=f"Turun ({RATE_THRESHOLD_FALLING} cm/min)", annotation_position="bottom right", annotation_font_color="green")

        min_rate_data = df_graph_data['delta_per_min'].dropna().min() if not df_graph_data['delta_per_min'].dropna().empty else RATE_THRESHOLD_FALLING
        max_rate_data = df_graph_data['delta_per_min'].dropna().max() if not df_graph_data['delta_per_min'].dropna().empty else RATE_THRESHOLD_DANGER_NO_RAIN
        y_axis_min = min(min_rate_data, RATE_THRESHOLD_FALLING) - 2
        y_axis_max = max(max_rate_data, RATE_THRESHOLD_DANGER_NO_RAIN) + 2

        xaxis_title = "Waktu"
        if resample_freq == 'D': xaxis_title = "Tanggal"
        elif resample_freq == '15min': xaxis_title = "Waktu (15 Menit)"
        elif resample_freq == '30min': xaxis_title = "Waktu (30 Menit)"

        fig_rate_avg.update_layout(
            title=f'Grafik Laju Perubahan Ketinggian Air',
            yaxis_title='Rata-Rata Laju Perubahan (cm/menit)',
            xaxis_title=xaxis_title,
            yaxis_range=[y_axis_min, y_axis_max],
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            margin=dict(l=50, r=50, t=50, b=50),
            hovermode="x unified"
        )
        rate_graph_placeholder.plotly_chart(fig_rate_avg, use_container_width=True)
    elif data_valid:
        rate_graph_placeholder.info("Data rata-rata laju perubahan tidak tersedia.")

    fig_temp_hum_avg = go.Figure()
    temp_trace_added = False
    hum_trace_added = False
    if not df_graph_data.empty and 'temperature' in df_graph_data.columns and not df_graph_data['temperature'].isnull().all():
        fig_temp_hum_avg.add_trace(go.Bar(x=df_graph_data.index, y=df_graph_data['temperature'], name='Rata-Rata Suhu (°C)', marker_color='#ef4444'))
        temp_trace_added = True
    if not df_graph_data.empty and 'humidity' in df_graph_data.columns and not df_graph_data['humidity'].isnull().all():
        fig_temp_hum_avg.add_trace(go.Bar(x=df_graph_data.index, y=df_graph_data['humidity'], name='Rata-Rata Kelembaban (%)', marker_color='#f59e0b'))
        hum_trace_added = True

    if temp_trace_added or hum_trace_added:
        xaxis_title = "Waktu"
        if resample_freq == 'D': xaxis_title = "Tanggal"
        elif resample_freq == '15min': xaxis_title = "Waktu (15 Menit)"
        elif resample_freq == '30min': xaxis_title = "Waktu (30 Menit)"

        fig_temp_hum_avg.update_layout(
            title=f'Grafik Suhu & Kelembaban',
            xaxis_title=xaxis_title,
            yaxis_title='Rata-Rata Nilai',
            barmode='group',
            legend_title_text='Metrik',
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            margin=dict(l=40, r=20, t=40, b=40),
            hovermode="x unified"
        )
        temp_hum_graph_placeholder.plotly_chart(fig_temp_hum_avg, use_container_width=True)
    elif data_valid:
        temp_hum_graph_placeholder.info("Data rata-rata suhu/kelembaban tidak tersedia.")

    fig_turbidity_avg = go.Figure()
    if not df_graph_data.empty and 'turbidity_voltage' in df_graph_data.columns and not df_graph_data['turbidity_voltage'].isnull().all():
        fig_turbidity_avg.add_trace(go.Scatter(
            x=df_graph_data.index,
            y=df_graph_data['turbidity_voltage'],
            mode='lines+markers',
            name='Rata-Rata Kekeruhan (V)',
            line=dict(color='#a16207', width=2),
            marker=dict(color='#a16207', size=5)
        ))

        fig_turbidity_avg.add_hline(y=TURBIDITY_CLEAR_THRESHOLD_V, line_dash="dot", line_color="green",
                                   annotation_text="Batas Jernih", annotation_position="bottom right",
                                   annotation_font_color="green")

        min_turb_data = df_graph_data['turbidity_voltage'].dropna().min() if not df_graph_data['turbidity_voltage'].dropna().empty else 0
        max_turb_data = df_graph_data['turbidity_voltage'].dropna().max() if not df_graph_data['turbidity_voltage'].dropna().empty else 4
        y_axis_min_turb = min(min_turb_data, 0) - 0.2
        y_axis_max_turb = max(max_turb_data, TURBIDITY_CLEAR_THRESHOLD_V) + 0.5

        xaxis_title = "Waktu"
        if resample_freq == 'D': xaxis_title = "Tanggal"
        elif resample_freq == '15min': xaxis_title = "Waktu (15 Menit)"
        elif resample_freq == '30min': xaxis_title = "Waktu (30 Menit)"

        fig_turbidity_avg.update_layout(
            title=f'Grafik Kekeruhan Air',
            yaxis_title='Rata-Rata Tegangan Sensor (V)',
            xaxis_title=xaxis_title,
            yaxis_range=[y_axis_min_turb, y_axis_max_turb],
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            margin=dict(l=50, r=50, t=50, b=50),
            hovermode="x unified"
        )
        turbidity_graph_placeholder.plotly_chart(fig_turbidity_avg, use_container_width=True)
    elif data_valid:
        turbidity_graph_placeholder.info("Data rata-rata kekeruhan tidak tersedia.")

    map_subheader_placeholder.subheader("Lokasi Sungai")
    if selected_river_coords:
        river_lat = selected_river_coords.get('latitude')
        river_lon = selected_river_coords.get('longitude')
        if river_lat is not None and river_lon is not None:
            map_df = pd.DataFrame({
                'lat': [river_lat],
                'lon': [river_lon],
                'nama': [selected_river_name]
            })
            with map_placeholder:
                st.map(map_df, zoom=14)
        else:
            with map_placeholder:
                st.info(f"Data koordinat tidak tersedia untuk {selected_river_name}.")
    else:
        with map_placeholder:
            st.info("Data koordinat tidak ditemukan untuk sungai yang dipilih.")

    time.sleep(60)
    st.rerun()

if __name__ == "__main__":
    main()