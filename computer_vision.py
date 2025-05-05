# computer_vision.py
import streamlit as st
from PIL import Image
import io
import base64
import google.generativeai as genai
import numpy as np
import requests
import time
import json

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    st.error(f"Gagal mengkonfigurasi atau memuat model: {e}")
    gemini_model = None

ESP32_CAPTURE_URL = "http://192.168.75.206/capture"

def capture_image_from_esp32(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        img_pil = Image.open(io.BytesIO(response.content))
        if img_pil is None:
            st.error("⚠️ Gagal decode gambar dari ESP32-CAM menggunakan PIL.")
            return None
        return img_pil
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Maaf, Kamera ESP32-CAM sedang tidak aktif.")
        return None
    except Exception as e:
        st.error(f"⚠️ Terjadi kesalahan saat mengambil atau memproses gambar ESP32: {e}")
        return None


def get_gemini_analysis(image_pil):
    if gemini_model is None:
        return False, -1, "Model AI tidak tersedia."

    try:
        prompt = """
        Analisis gambar permukaan air (sungai, danau, laut) ini. Berikan DUA output dalam format JSON valid:
        1.  'valid_surface': boolean (true jika ini adalah gambar permukaan air yang relevan, false jika tidak, contohnya gambar dalam ruangan, langit, atau objek tidak relevan).
        2.  'trash_scale': integer antara 0 dan 100 yang merepresentasikan *kepadatan visual* sampah yang terlihat mengapung atau di tepi air (fokus pada benda buatan manusia seperti botol plastik, kantong, styrofoam, dll.). Abaikan objek alami (daun, kayu, batu, hewan).
            Skala Kepadatan:
            0 = Tidak ada sampah sama sekali terlihat.
            1-10 = Sampah sangat jarang, mungkin 1-2 item kecil.
            11-30 = Sedikit sampah tersebar.
            31-50 = Cukup banyak sampah terlihat di beberapa area.
            51-70 = Banyak sampah, cukup mendominasi beberapa bagian gambar.
            71-90 = Sangat banyak sampah, menutupi sebagian besar area air yang terlihat.
            91-100 = Permukaan air hampir tertutup penuh oleh sampah.
            Pertimbangkan juga ukuran dan jenis sampah saat menilai kepadatan. Jika gambar sangat blur atau tidak jelas sehingga sulit dinilai, berikan estimasi terbaikmu atau nilai tengah jika ragu.

        Contoh Output: {"valid_surface": true, "trash_scale": 25}
        Contoh Output: {"valid_surface": true, "trash_scale": 80}
        Contoh Output: {"valid_surface": false, "trash_scale": 0}
        Outputkan HANYA JSON valid tanpa teks atau markdown lain di sekitarnya.
        """
        response = gemini_model.generate_content([prompt, image_pil])
        response.resolve()

        json_str_match = response.text.strip()
        if json_str_match.startswith("```json"):
            json_str_match = json_str_match[7:]
        if json_str_match.endswith("```"):
            json_str_match = json_str_match[:-3]
        json_str_match = json_str_match.strip()

        result_json = json.loads(json_str_match)
        is_valid = result_json.get('valid_surface', False)
        scale = result_json.get('trash_scale', -1)

        if not isinstance(is_valid, bool): is_valid = False
        if not isinstance(scale, int) or not (0 <= scale <= 100): scale = -1

        analysis_text = f"Validasi Permukaan Air: {'Ya' if is_valid else 'Tidak'}. Estimasi Skala Sampah: {scale}/100"
        return is_valid, scale, analysis_text

    except json.JSONDecodeError:
        error_msg = "Gagal memparsing respons JSON dari AI."
        print(f"Raw Gemini Response: {response.text}")
        st.error(error_msg)
        return False, -1, error_msg
    except Exception as e:
        error_msg = f"Terjadi kesalahan saat analisis Gemini: {e}"
        st.error(error_msg)
        return False, -1, error_msg

def scale_to_text(scale):
    if scale == 0: return "Tidak Ada"
    elif 1 <= scale <= 30: return "Sedikit"
    elif 31 <= scale <= 70: return "Banyak"
    elif 71 <= scale <= 100: return "Sangat Banyak"
    else: return "Tidak Terdeteksi/Error"


def main():
    st.markdown(
        "<h2>Deteksi Sampah di Sungai</h2>",
        unsafe_allow_html=True
    )

    st.sidebar.header("Sumber Gambar")
    source_option = st.sidebar.radio(
        "Pilih metode input gambar:",
        ("Unggah Gambar", "Ambil dari ESP32-CAM")
    )

    image_input_pil = None
    caption = ""

    if source_option == "Unggah Gambar":
        uploaded_file = st.sidebar.file_uploader("Pilih file gambar:", type=["jpg", "jpeg", "png"], key="file_uploader")
        if uploaded_file is not None:
            try:
                image_bytes = uploaded_file.getvalue()
                image_input_pil = Image.open(io.BytesIO(image_bytes))
                caption = f"Gambar Diunggah: {uploaded_file.name}"
            except Exception as e:
                 st.error(f"Error saat memproses file unggahan: {e}")
                 image_input_pil = None

    elif source_option == "Ambil dari ESP32-CAM":
        # st.sidebar.info(f"Akan mengambil gambar dari:\n{ESP32_CAPTURE_URL}")
        if st.sidebar.button("📸 Ambil Gambar dari ESP32", key="esp32_capture"):
            with st.spinner(f"Mengambil gambar dari ESP32-CAM..."):
                 image_input_pil = capture_image_from_esp32(ESP32_CAPTURE_URL)
                 if image_input_pil is not None:
                      caption = "Gambar dari ESP32-CAM"
                 else:
                      caption = "Gagal mengambil gambar dari ESP32-CAM"


    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Gambar Input")
        if image_input_pil:
            st.image(image_input_pil, caption=caption, use_container_width=True)
        else:
            st.info("Silakan pilih sumber gambar dan unggah atau ambil gambar.")

    with col2:
        st.subheader("Hasil Analisis AI")
        result_text_placeholder = st.empty()
        analyze_button_placeholder = st.empty()

        if image_input_pil is not None:
             if gemini_model:
                 if analyze_button_placeholder.button("Analisis dengan AI", key="analyze_gemini"):
                     with st.spinner("Menganalisis gambar dengan AI..."):
                         is_valid, trash_scale, analysis_msg = get_gemini_analysis(image_input_pil)

                     if not is_valid:
                         result_text_placeholder.error("Gambar tidak valid. AI mendeteksi ini bukan permukaan air sungai/danau.")
                     elif trash_scale != -1:
                          trash_text = scale_to_text(trash_scale)
                          result_text_placeholder.success(f"Estimasi Kepadatan Sampah: **{trash_text}** (Skala AI: {trash_scale}/100)")
                     else:
                          result_text_placeholder.error(f"AI tidak dapat memberikan estimasi skala sampah. ({analysis_msg})")
             else:
                  result_text_placeholder.error("Model AI tidak berhasil dimuat.")
        else:
              result_text_placeholder.info("Menunggu gambar untuk dianalisis.")


if __name__ == "__main__":
    main()