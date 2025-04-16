import streamlit as st
import google.generativeai as genai
import random
from datetime import datetime

# Konfigurasi API Gemini
api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

# Fungsi untuk menghasilkan data random (sementara)
def get_random_data():
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "distance": random.uniform(10, 50),  # Invers ketinggian air
        "raindrop": random.choice([0, 1]),
        "temperature": random.uniform(20, 35),
        "humidity": random.uniform(40, 90)
    }

# Fungsi untuk menghasilkan jawaban
def get_answer(prompt, data):
    rain_text = "hujan" if data["raindrop"] == 1 else "tidak hujan"
    context = f"Pada {data['timestamp']}, ketinggian air sekitar {data['distance']:.2f} cm, " \
              f"status hujan: {rain_text}, suhu: {data['temperature']}°C, kelembaban: {data['humidity']}%."
    final_prompt = f"""
Berikut ini adalah data sensor air yang telah tercatat:
{context}

Berdasarkan data tersebut, jawab pertanyaan berikut ini:
{prompt}

Jawabanmu harus ringkas, jelas, dan gunakan bahasa yang mudah dimengerti.
"""
    response = model.generate_content(final_prompt)
    return response.text.strip()

def main():
    st.title("Chatbot Kesehatan Sungai")

    # Inisialisasi state
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Halo! Tanya aku tentang kondisi sungai! 😊"}]
    if "has_user_asked" not in st.session_state:
        st.session_state.has_user_asked = False

    # Tampilkan pesan
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Saran pertanyaan
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

    # Input pengguna
    user_input = st.chat_input("Tanyakan sesuatu...")
    prompt = st.session_state.get("selected_prompt", user_input)
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        answer = get_answer(prompt, get_random_data())
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)
        st.session_state.has_user_asked = True
        if "selected_prompt" in st.session_state:
            del st.session_state.selected_prompt

if __name__ == "__main__":
    main()