import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, WebRtcMode
import av
import cv2
import torch
import numpy as np
import urllib.request
import threading
import time
import requests
import streamlit as st
import cv2
import torch
import numpy as np
import requests
import time

# Load YOLOv5 model once
model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
model.conf = 0.4

# Function to capture a single image from ESP32-CAM
def capture_image_from_esp32(url):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            # Convert the image to numpy array
            img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            return img
        else:
            st.error(f"⚠️ Gagal mengakses gambar dari ESP32-CAM. Status: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"⚠️ Terjadi kesalahan saat mengambil gambar: {e}")
        return None

# Function to stream from ESP32-CAM with frame updates
def stream_esp32(url, frame_window):
    while True:
        frame = capture_image_from_esp32(url)
        if frame is None:
            st.warning("⚠️ Tidak bisa mendapatkan gambar dari ESP32-CAM.")
            break

        # YOLOv5 object detection
        results = model(frame)
        detections = results.xyxy[0]

        # Draw bounding boxes and labels
        for *box, conf, cls in detections:
            x1, y1, x2, y2 = map(int, box)
            label = f"{model.names[int(cls)]} {conf:.2f}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Display object count
        cv2.putText(frame, f"Jumlah objek: {len(detections)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        # Update the image display in Streamlit
        frame_window.image(frame, channels="BGR")
        time.sleep(0.1)  # Delay to prevent too fast looping

# Main function for Streamlit app
def main():
    st.title("🚮 Deteksi Sampah di Sungai")

    with st.sidebar.expander("🔧 Pengaturan Kamera"):
        CAM_SOURCE = st.radio("🎥 Pilih Sumber Kamera", ("Kamera Laptop/USB", "ESP32-CAM"))
        esp32_url = st.text_input("🌐 URL Stream ESP32-CAM", "http://192.168.75.206/capture")

    if CAM_SOURCE == "Kamera Laptop/USB":
        # Use the webrtc_streamer for webcam/USB camera
        st.warning("Fitur streaming dari Kamera Laptop/USB belum diimplementasikan.")
    else:
        st.warning("ESP32-CAM aktif. Menyambungkan ke stream...")
        FRAME_WINDOW = st.empty()

        # Directly stream ESP32-CAM in the main thread to prevent threading issues
        stream_esp32(esp32_url, FRAME_WINDOW)

if __name__ == "__main__":
    main()
