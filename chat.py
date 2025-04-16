import streamlit as st
import google.generativeai as genai
from datetime import datetime
from utils import get_mongo_data_for_chat

api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

def get_answer(prompt, data_list):
    if not data_list:
        return "Maaf, saat ini tidak ada data sensor yang tersedia untuk menjawab pertanyaan kamu."

    latest_timestamp = data_list[-1]["timestamp"]

    context = f"Data berikut diambil dari catatan sensor sungai. Data terakhir tercatat pada {latest_timestamp}.\n"
    for data in data_list:
        rain_text = "hujan" if data["raindrop"] == 1 else "tidak hujan"
        warning_text = "Ada peringatan banjir" if data.get("warning", 0) == 1 else "Tidak ada peringatan banjir"
        context += (
            f"- {data['timestamp']}: Ketinggian air {data['distance']:.2f} cm, "
            f"{rain_text}, Suhu {data['temperature']}°C, Kelembaban {data['humidity']}%, "
            f"{warning_text}\n"
        )

    final_prompt = f"""
Kamu adalah chatbot pemantau kesehatan sungai yang hanya boleh memberikan jawaban berdasarkan data sensor yang tersedia.

Kamu adalah chatbot yang dibuat oleh Tim "stars we chase" dalam mengikuti Bootcamp Samsung Innovation Campus Batch 6 yang diselenggarakan oleh Hacktiv8. Anggotanya adalah:
- Muhammad Alfarrel Arya Mahardika
- Muhammad Bintang Saputra
- Muhamad Beril Fikri Widjaya
- Rifqi Raehan Hermawan
Semua anggota berasal dalam 1 kampus sama yaitu Politeknik Elektronika Negeri Surabaya.

Tentang Aplikasi 'River Health Monitoring' ini:
Kami ingin mengembangkan alat pendeteksi dini bencana banjir beserta monitoring kesehatan air sungai, agar terdapat peringatan sejak dini untuk mencegah munculnya bencana banjir dan untuk memantau kesehatan sungai.

Jika user menanyakan tentang suatu data selalu gunakan referensi kapan data terakhir diambil. Gunakan format 'Tanggal Nama Bulan Tahun, hours:minute'. Sehingga, menjadi Berdasarkan data terakhir yang diambil di ...

{context}

Berdasarkan data tersebut, jawab pertanyaan berikut ini:
{prompt}

Instruksi:
- Jawaban harus ringkas dan jelas.
- Jangan memberikan informasi tambahan yang tidak tersedia.
- Jika data tidak mencukupi untuk menjawab, sampaikan dengan jujur.
- Jawaban hanya berdasarkan data di atas.
- Jangan memberikan asumsi atau informasi tambahan di luar data.
- Jika data tidak tersedia untuk menjawab, katakan dengan jujur bahwa data tidak tersedia.
"""
    response = model.generate_content(final_prompt)
    return response.text.strip()


def main():
    st.title("Chatbot Kesehatan Sungai")

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Halo! Tanyakan aku tentang kondisi sungai berdasarkan data sensor ya! 😊"}]
    if "has_user_asked" not in st.session_state:
        st.session_state.has_user_asked = False

    mongo_data = get_mongo_data_for_chat()
    if not mongo_data:
        st.error("Data dari sensor tidak tersedia.")
        return

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not st.session_state.has_user_asked:
        st.markdown("💡 **Coba tanyakan ini:**")
        cols = st.columns(3)
        suggestions = ["Apakah sedang hujan?", "Berapa ketinggian air?", "Berapa suhu saat ini?"]
        for i, suggestion in enumerate(suggestions):
            with cols[i]:
                if st.button(suggestion, key=f"suggestion_{i}"):
                    st.session_state.selected_prompt = suggestion
                    st.session_state.has_user_asked = True
                    st.rerun()

    user_input = st.chat_input("Tanyakan sesuatu...")
    prompt = st.session_state.get("selected_prompt", user_input)
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        answer = get_answer(prompt, mongo_data)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)
        st.session_state.has_user_asked = True
        if "selected_prompt" in st.session_state:
            del st.session_state.selected_prompt


if __name__ == "__main__":
    main()