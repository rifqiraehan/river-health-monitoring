import machine
import time
import dht
import urequests
import network
from machine import Pin, PWM, ADC

# ------------------- WiFi -------------------
WIFI_SSID = 'akanesan'
WIFI_PASS = '12345678'

# ------------------- Server Configuration -------------------
SERVER_IP = "192.168.208.169"  # IP komputer Anda
SERVER_PORT = "5000"
SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}/sensor"

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        timeout = 10  # 10 detik timeout
        start = time.time()
        while not wlan.isconnected() and (time.time() - start) < timeout:
            time.sleep(0.5)
        if not wlan.isconnected():
            print("Failed to connect to WiFi")
            return False
    print("Connected, IP address:", wlan.ifconfig()[0])
    return True

# ------------------- Ubidots -------------------
UBIDOTS_TOKEN = "BBUS-Iw1T4vMtSFQeyp0X7xKVmb8VNXux2x"
DEVICE_LABEL = "esp32_assignmentstage3"

def send_to_ubidots(temperature, humidity, distance, warning, raindrop):
    url = f"http://industrial.api.ubidots.com/api/v1.6/devices/{DEVICE_LABEL}/"
    headers = {
        'X-Auth-Token': UBIDOTS_TOKEN,
        'Content-Type': 'application/json'
    }
    payload = {
        "temperature": temperature,
        "humidity": humidity,
        "distance": distance,
        "warning": warning,
        "RainDrop": raindrop
    }
    try:
        response = urequests.post(url, json=payload, headers=headers)
        print("Ubidots Data sent:", response.text)
        response.close()
    except Exception as e:
        print("Failed to send data to Ubidots:", e)

# ------------------- Server -------------------
def send_to_server(temperature, humidity, distance, warning, raindrop, retries=3):
    headers = {"Content-Type": "application/json"}
    payload = {
        "temperature": temperature,
        "humidity": humidity,
        "distance": distance,
        "warning": warning,
        "raindrop": raindrop
    }
    print(f"Sending to server: {SERVER_URL} with payload: {payload}")
    for attempt in range(retries):
        try:
            response = urequests.post(SERVER_URL, json=payload, headers=headers)
            print("Server Response:", response.status_code, response.text)
            response.close()
            return True
        except Exception as e:
            print(f"Attempt {attempt + 1}/{retries} - Failed to send data to server:", e)
            if attempt < retries - 1:
                time.sleep(1)  # Tunggu sebelum retry
    print("All attempts to send data to server failed")
    return False

# ------------------- HC-SR04 Class -------------------
class HCSR04:
    def __init__(self, trigger_pin, echo_pin, echo_timeout_us=1000000):
        self.echo_timeout_us = echo_timeout_us
        self.trigger = Pin(trigger_pin, mode=Pin.OUT)
        self.trigger.value(0)
        self.echo = Pin(echo_pin, mode=Pin.IN)

    def _send_pulse_and_wait(self):
        self.trigger.value(0)
        time.sleep_us(5)
        self.trigger.value(1)
        time.sleep_us(10)
        self.trigger.value(0)
        try:
            pulse_time = machine.time_pulse_us(self.echo, 1, self.echo_timeout_us)
            return pulse_time
        except OSError as ex:
            if ex.args[0] == 110:
                raise OSError('Out of range')
            raise ex

    def distance_cm(self):
        try:
            pulse_time = self._send_pulse_and_wait()
            return (pulse_time / 2) / 29.1
        except:
            return 999  # fallback jarak error

# ------------------- Read DHT11 -------------------
def read_dht(dht_sensor):
    for _ in range(3):  # Coba 3 kali
        try:
            dht_sensor.measure()
            return dht_sensor.temperature(), dht_sensor.humidity()
        except OSError as e:
            print("Retrying DHT read...")
            time.sleep(2)
    print("Failed to read DHT sensor")
    return None, None

# ------------------- Inisialisasi -------------------
if not connect_wifi():
    print("Restarting due to WiFi failure...")
    machine.reset()

ultrasonic = HCSR04(trigger_pin=13, echo_pin=12)
dht_sensor = dht.DHT11(Pin(25))
led = Pin(2, Pin.OUT)
buzzer = PWM(Pin(14), freq=1000)
buzzer.duty(0)

# RainDrop sensor analog (D34)
raindrop_adc = ADC(Pin(34))
raindrop_adc.atten(ADC.ATTN_11DB)  # untuk jangkauan 0 - 3.3V
raindrop_adc.width(ADC.WIDTH_10BIT)  # resolusi 10 bit: 0-1023

# ------------------- Loop -------------------
while True:
    try:
        # Baca DHT11
        temperature, humidity = read_dht(dht_sensor)
        if temperature is None or humidity is None:
            print("Skipping data send due to DHT failure")
            time.sleep(1)
            continue

        # Baca Jarak
        distance = ultrasonic.distance_cm()

        # Baca RainDrop dan balikkan nilai pembacaannya
        raindrop = 1023 - raindrop_adc.read()

        print("Temp:", temperature, "°C | Humid:", humidity, "% | Jarak:", distance, "cm | RainDrop:", raindrop)

        # Logic Warning
        if distance != 999 and distance <= 10:
            warning = 1
            buzzer.duty(512)
            led.on()
        else:
            warning = 0
            buzzer.duty(0)
            led.off()

        # Kirim ke Ubidots
        send_to_ubidots(temperature, humidity, distance, warning, raindrop)

        # Kirim ke Server
        send_to_server(temperature, humidity, distance, warning, raindrop)

    except Exception as e:
        print("General error:", e)

    time.sleep(1)
