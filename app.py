import streamlit as st
import dashboard as dashboard
import computer_vision as cv
import chat as chat
import report as report

st.set_page_config(page_title="River Health Monitoring", layout="wide")

st.sidebar.title("Navigasi")
page_options = ["Dashboard", "Deteksi Sampah", "Chat AI", "Laporan Warga"]
page = st.sidebar.selectbox("Pilih Menu", page_options)

if page == "Dashboard":
    st.sidebar.markdown("Menampilkan data sensor terkini dan grafik tren kondisi sungai.")
elif page == "Deteksi Sampah":
    st.sidebar.markdown("Mendeteksi sampah di sungai menggunakan gambar yang diunggah.")
elif page == "Chat AI":
    st.sidebar.markdown("Berinteraksi dengan chatbot untuk analisis data sensor.")
elif page == "Laporan Warga":
    st.sidebar.markdown("Mengirimkan laporan kondisi sungai langsung dari warga.")

if page == "Dashboard":
    dashboard.main()
elif page == "Deteksi Sampah":
    cv.main()
elif page == "Chat AI":
    chat.main()
elif page == "Laporan Warga":
    report.main()