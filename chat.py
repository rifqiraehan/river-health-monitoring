import streamlit as st
import google.generativeai as genai
from datetime import datetime, timedelta
from mongo_utils import get_all_river_summaries
from bson import ObjectId

api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)
try:
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    st.error(f"Gagal memuat model Gemini: {e}")
    st.stop()

DAYS_OF_HISTORY_FOR_CHATBOT = 7

def get_answer(chat_history, current_prompt, context_summary):
    if not context_summary or "Terjadi kesalahan" in context_summary:
        return f"Maaf, terjadi kesalahan saat memuat data untuk menjawab pertanyaan Anda: {context_summary}"
    elif "Tidak ada data" in context_summary and len(context_summary.split("###")) <= 2:
         return f"Maaf, tidak ada data sensor maupun laporan warga yang ditemukan untuk menjawab pertanyaan Anda saat ini."


    formatted_history = []
    for msg in chat_history:
        role = "model" if msg["role"] == "assistant" else msg["role"]
        formatted_history.append({"role": role, "parts": [msg["content"]]})

    if formatted_history and "Halo! Saya RiverBot" in formatted_history[0]["parts"][0]:
         formatted_history.pop(0)


    system_instruction = f"""
Kamu adalah chatbot AI pemantau kesehatan sungai bernama 'RiverBot'. Tugasmu adalah menjawab pertanyaan pengguna **berdasarkan ringkasan data sensor DAN ringkasan laporan warga** selama {DAYS_OF_HISTORY_FOR_CHATBOT} hari terakhir yang diberikan untuk **beberapa lokasi sungai**. Kamu juga harus **memperhatikan riwayat percakapan sebelumnya** untuk menjaga konteks.

Informasi Pengembang:
Chatbot ini dibuat oleh Tim "stars we chase" (Bootcamp Samsung Innovation Campus Batch 6 - Hacktiv8):
- Muhammad Alfarrel Arya Mahardika
- Muhammad Bintang Saputra
- Muhamad Beril Fikri Widjaya
- Rifqi Raehan Hermawan
Semua anggota berasal dari Politeknik Elektronika Negeri Surabaya (PENS).
Aplikasi ini bertujuan untuk deteksi dini banjir dan monitoring kesehatan sungai.

Ringkasan Data Sensor dan Laporan Warga dari Semua Lokasi Sungai (Periode: {DAYS_OF_HISTORY_FOR_CHATBOT} hari terakhir. Gunakan ini sebagai FAKTA UTAMA):
{context_summary}

Instruksi Penting:
- Jawablah pertanyaan pengguna terakhir ({current_prompt}) berdasarkan **konteks percakapan sebelumnya** DAN **ringkasan data sensor serta laporan warga**.
- Prioritaskan informasi dari **ringkasan data** sebagai sumber fakta. Bandingkan data sensor dengan laporan warga jika relevan dan diminta.
- Jika pertanyaan pengguna merujuk pada percakapan sebelumnya, gunakan history untuk memahami rujukannya, lalu jawab berdasarkan data yang tersedia.
- **Jangan** membuat asumsi, menambahkan informasi eksternal, atau data historis yang **tidak ada** dalam ringkasan {DAYS_OF_HISTORY_FOR_CHATBOT} hari terakhir.
- Jika ringkasan tidak berisi informasi yang cukup untuk menjawab, katakan bahwa data spesifik tersebut tidak tersedia dalam ringkasan periode ini.
- Selalu sebutkan nama sungai yang relevan dalam jawabanmu.
- Sebutkan tanggal data terakhir (baik sensor maupun laporan) jika relevan atau ditanya.
- Jangan mengulangi informasi pengembang kecuali ditanya secara spesifik.
- Jangan menyebutkan nilai sensor mentah kecuali itu bagian dari ringkasan (rata-rata, maks, min). Cukup sebutkan kondisinya.
- Tetap ringkas dan jelas.
"""

    model_instance = genai.GenerativeModel('gemini-2.0-flash')
    chat = model_instance.start_chat(history=formatted_history)

    try:
        full_context_for_prompt = f"{system_instruction}\n\n---\n\nPrompt Pengguna: {current_prompt}"
        response = chat.send_message(full_context_for_prompt)

        return response.text.strip() if hasattr(response, 'text') else "Maaf, terjadi masalah dalam menghasilkan jawaban."
    except Exception as e:
        st.error(f"Error saat menghubungi AI: {e}")
        return "Maaf, terjadi kesalahan saat mencoba menghasilkan jawaban dari AI."


def main():
    st.markdown(
        "<h2>Chatbot Kesehatan Sungai (RiverBot)</h2>",
        unsafe_allow_html=True
    )

    with st.spinner(f"Memuat ringkasan data {DAYS_OF_HISTORY_FOR_CHATBOT} hari terakhir..."):
        data_summary, all_data_available = get_all_river_summaries(days_history=DAYS_OF_HISTORY_FOR_CHATBOT)

    if not data_summary or "Terjadi kesalahan" in data_summary:
        st.error(f"Gagal memuat data untuk chatbot: {data_summary}")
        st.stop()
    # elif not all_data_available:
    #      st.warning("Beberapa data (sensor atau laporan warga) mungkin tidak tersedia untuk semua sungai dalam periode ini.")


    if "messages_chat_multi" not in st.session_state:
        st.session_state.messages_chat_multi = [{"role": "assistant", "content": "Halo! Saya RiverBot. Tanyakan tentang kondisi sungai yang dipantau berdasarkan data sensor dan laporan warga terakhir ya! 😊"}]


    user_input = st.chat_input("Tanyakan tentang kondisi sungai...")
    prompt = st.session_state.get("selected_prompt_chat_multi", user_input)

    if prompt:
        st.session_state.messages_chat_multi.append({"role": "user", "content": prompt})

        with st.spinner("RiverBot sedang berpikir..."):
            history_for_llm = st.session_state.messages_chat_multi[:-1]
            answer = get_answer(history_for_llm, prompt, data_summary)

        st.session_state.messages_chat_multi.append({"role": "assistant", "content": answer})

        if "selected_prompt_chat_multi" in st.session_state:
            del st.session_state.selected_prompt_chat_multi
        st.rerun()

    for msg in st.session_state.messages_chat_multi:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


    if len(st.session_state.messages_chat_multi) <= 1:
        st.markdown("💡 **Coba tanyakan ini:**")
        cols = st.columns(5)
        suggestions = [
            "Bagaimana status terbaru semua sungai menurut sensor dan laporan?",
            "Apakah ada laporan banjir di Sungai Keputih?",
            "Bandingkan kondisi sampah yang dilaporkan warga di kedua sungai",
            "Apakah status sensor sesuai dengan laporan warga terakhir?",
            "Bagaimana kondisi umum sungai minggu ini?"
        ]
        for i, suggestion in enumerate(suggestions):
            col_index = i % len(cols)
            with cols[col_index]:
                if st.button(suggestion, key=f"suggestion_chat_multi_{i}"):
                    st.session_state.selected_prompt_chat_multi = suggestion
                    st.rerun()


if __name__ == "__main__":
    main()