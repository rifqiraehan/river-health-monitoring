import streamlit as st
from datetime import datetime
from mongo_utils import save_report, save_report_with_photo_gridfs, get_river_locations
import io
from streamlit_geolocation import streamlit_geolocation
import time
from bson import ObjectId
import math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance_km = R * c
    return distance_km

def main():
    st.markdown(
        "<h2>Laporan Warga</h2>",
        unsafe_allow_html=True
    )
    st.write("Gunakan formulir ini untuk melaporkan kondisi terkini di sekitar sungai.")
    st.info("Untuk mengirim laporan, Anda **harus** berada dalam radius 1 km dari lokasi sungai yang dipilih, mengizinkan akses lokasi, dan mengambil foto kondisi sungai.")

    river_locations_data = get_river_locations()
    if not river_locations_data:
        st.error("Gagal memuat daftar lokasi sungai. Tidak dapat mengirim laporan.")
        st.stop()

    river_coords_map = {str(river['_id']): {'latitude': river['latitude'], 'longitude': river['longitude']}
                        for river in river_locations_data if 'latitude' in river and 'longitude' in river}
    river_names = [river['nama'] for river in river_locations_data]
    river_id_map = {river['nama']: str(river['_id']) for river in river_locations_data}

    kondisi_sungai_options = [
        "Aman", "Banjir", "Air Meluap", "Warna Berubah", "Bau Menyengat",
        "Tumpukan Sampah", "Ikan Mati", "Saluran Tersumbat", "Lainnya"
    ]
    jumlah_sampah_options = ["Tidak Ada", "Sedikit", "Banyak", "Sangat Banyak"]

    with st.form("laporan_warga_form", clear_on_submit=False):
        selected_river_name = st.selectbox("Pilih Lokasi Sungai", options=river_names, index=None, placeholder="Pilih sungai yang dilaporkan...")
        nama_lengkap = st.text_input("Nama Pelapor", max_chars=100)
        alamat = st.text_area("Alamat Pelapor (Opsional)")
        telepon = st.text_input("Nomor Telepon (Contoh: 08123456789)", max_chars=15)
        camera_photo = st.camera_input("Ambil Foto Kondisi Sungai (Wajib)")
        kondisi_sungai = st.multiselect("Kondisi Sungai (Pilih satu atau lebih)", kondisi_sungai_options)
        jumlah_sampah = st.selectbox("Jumlah Sampah", jumlah_sampah_options)
        deskripsi = st.text_area("Deskripsi Tambahan (Opsional)")

        submitted = st.form_submit_button("Kirim Laporan")

        if submitted:
            location_data = None
            with st.spinner("Memeriksa lokasi..."):
                 location_data = streamlit_geolocation()

            is_valid = True
            latitude = None
            longitude = None
            selected_sungai_id = None
            selected_sungai_id_str = None

            if not selected_river_name:
                 st.error("Lokasi Sungai wajib dipilih.")
                 is_valid = False
            else:
                 selected_sungai_id_str = river_id_map.get(selected_river_name)
                 if not selected_sungai_id_str:
                     st.error("Nama sungai yang dipilih tidak valid.")
                     is_valid = False
                 else:
                     try:
                         selected_sungai_id = ObjectId(selected_sungai_id_str)
                     except Exception:
                         st.error("Format ID Sungai tidak valid.")
                         is_valid = False

            if not (location_data and location_data.get('latitude') and location_data.get('longitude')):
                st.error("Gagal mengambil lokasi. Pastikan izin lokasi diberikan dan layanan lokasi aktif. Laporan tidak dapat dikirim.")
                is_valid = False

            if camera_photo is None:
                st.error("Foto kondisi sungai wajib diambil.")
                is_valid = False

            if is_valid:
                latitude = location_data['latitude']
                longitude = location_data['longitude']

                river_coords = river_coords_map.get(selected_sungai_id_str)
                if not river_coords:
                     st.error(f"Data koordinat tidak ditemukan untuk sungai '{selected_river_name}'. Laporan tidak dapat divalidasi jaraknya.")
                     is_valid = False
                else:
                     try:
                         river_lat = river_coords['latitude']
                         river_lon = river_coords['longitude']
                         distance_km = haversine(latitude, longitude, river_lat, river_lon)
                         st.info(f"Jarak Anda dari lokasi sungai '{selected_river_name}': {distance_km:.2f} km")
                         if distance_km > 1.0:
                             st.error(f"Anda terlalu jauh ({distance_km:.2f} km) dari lokasi sungai '{selected_river_name}'. Laporan hanya bisa dikirim dalam radius 1 km.")
                             is_valid = False
                     except KeyError:
                          st.error(f"Data koordinat (latitude/longitude) tidak lengkap untuk sungai '{selected_river_name}'.")
                          is_valid = False
                     except Exception as dist_err:
                          st.error(f"Gagal menghitung jarak: {dist_err}")
                          is_valid = False


            if is_valid:
                if not nama_lengkap:
                    st.error("Nama Pelapor wajib diisi.")
                    is_valid = False
                if not telepon:
                    st.error("Nomor Telepon wajib diisi.")
                    is_valid = False
                elif not telepon.isdigit():
                    st.error("Nomor Telepon harus berupa angka.")
                    is_valid = False
                if not kondisi_sungai:
                    st.error("Pilih setidaknya satu Kondisi Sungai.")
                    is_valid = False
                if not jumlah_sampah:
                    st.error("Jumlah Sampah wajib diisi.")
                    is_valid = False

            if is_valid:
                report_time = datetime.now()

                report_metadata = {
                    "timestamp": report_time,
                    "sungai_id": selected_sungai_id,
                    "nama_pelapor": nama_lengkap,
                    "alamat_pelapor": alamat if alamat else None,
                    "telepon_pelapor": telepon,
                    "latitude": latitude,
                    "longitude": longitude,
                    "kondisi_terpilih": kondisi_sungai,
                    "jumlah_sampah": jumlah_sampah,
                    "deskripsi": deskripsi if deskripsi else None,
                    "status_verifikasi": False
                }

                inserted_id = None
                process_message = "Mengunggah foto dan menyimpan laporan..."

                photo_data = camera_photo.getvalue()
                photo_filename = f"capture_{report_time.strftime('%Y%m%d_%H%M%S')}.jpg"
                photo_content_type = "image/jpeg"

                with st.spinner(process_message):
                    inserted_id = save_report_with_photo_gridfs(
                        report_metadata,
                        photo_data,
                        photo_filename,
                        photo_content_type
                    )

                if inserted_id:
                    st.success(f"Laporan berhasil dikirim! ID Laporan: {inserted_id}")
                else:
                    pass

if __name__ == "__main__":
    main()