# File: app.py
import streamlit as st
import dashboard as dashboard
import computer_vision as cv
import chat as chat

# Konfigurasi halaman
st.set_page_config(page_title="River Health Monitoring", layout="wide")

# Sidebar untuk navigasi
st.sidebar.title("Navigasi")
page = st.sidebar.selectbox("Pilih Menu", ["Dashboard", "Computer Vision", "Chatbot"])

if page == "Dashboard":
    st.sidebar.markdown("**Deskripsi:** Menampilkan data sensor terkini dan grafik tren ketinggian air, suhu, serta kelembaban.")
elif page == "Computer Vision":
    st.sidebar.markdown("**Deskripsi:** Mendeteksi sampah di sungai menggunakan gambar yang diunggah.")
elif page == "Chatbot":
    st.sidebar.markdown("**Deskripsi:** Berinteraksi dengan chatbot untuk mengetahui analisis data sensor dan kondisi sungai.")

# Memuat halaman yang dipilih
if page == "Dashboard":
    dashboard.main()
elif page == "Computer Vision":
    cv.main()
elif page == "Chatbot":
    chat.main()