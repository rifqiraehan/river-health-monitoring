# File: pages/_computer_vision.py
import streamlit as st
from PIL import Image
import io
import base64
import google.generativeai as genai

# Konfigurasi API Gemini
api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

def get_image_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str

def is_water_surface(image):
    """
    Memverifikasi apakah gambar menunjukkan permukaan air (sungai, danau, kolam).
    Mengembalikan True jika valid, False jika tidak.
    """
    try:
        prompt = "Periksa apakah gambar ini menunjukkan permukaan air seperti sungai, danau, atau kolam. Jawab hanya dengan 'Ya' jika ya, atau 'Tidak' jika tidak."
        response = model.generate_content([prompt, image])
        response.resolve()
        return response.text.strip().lower() == "ya"
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memverifikasi gambar: {e}")
        return False

def get_object_count(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))

        # Validasi apakah gambar menunjukkan permukaan air
        if not is_water_surface(image):
            return "Gambar tidak valid: Harap unggah gambar yang menunjukkan permukaan air sungai."

        # Jika valid, lanjutkan ke deteksi sampah
        prompt = "Analisis gambar sungai ini dan hitung jumlah sampah yang terdeteksi (seperti botol plastik, kantong plastik, atau benda buatan manusia lainnya). Abaikan benda alami seperti daun, kayu, atau batu. Outputkan hanya angka numerik total sampah yang terdeteksi (contoh: 5), tanpa teks tambahan. Jika tidak ada sampah yang terdeteksi, outputkan 0."
        response = model.generate_content([prompt, image])
        response.resolve()
        numeric_response = ''.join(filter(str.isdigit, response.text))
        return numeric_response if numeric_response else "Tidak dapat mendeteksi jumlah sampah."
    except Exception as e:
        return f"Terjadi kesalahan: {e}"

def main():
    st.title("Deteksi Sampah di Sungai")
    uploaded_file = st.file_uploader("Unggah gambar...", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        image_bytes = uploaded_file.read()
        image = Image.open(io.BytesIO(image_bytes))
        st.image(image, caption="Gambar yang diunggah.", use_container_width=True)
        if st.button("Deteksi Jumlah Sampah"):
            with st.spinner("Menganalisis gambar..."):
                result = get_object_count(image_bytes)
                st.subheader("Hasil Deteksi:")
                st.write(f"**{result}**")

if __name__ == "__main__":
    main()