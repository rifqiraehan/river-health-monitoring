import machine
import time
import dht
from machine import Pin, PWM, ADC, UART, I2C
import ssd1306
import network
import ujson
import sys
from umqtt.simple import MQTTClient

WIFI_SSID = "Yoru no Hajimarisa"
WIFI_PASSWORD = "bunnygirl"

MQTT_BROKER = "f6edeb4adb7c402ca7291dd7ef4d8fc5.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1747043871321"
MQTT_PASSWORD = "ab45PjNdISi;Bf9>2,G#"
MQTT_CLIENT_ID = "MicroPython_Sensor_001"
MQTT_SENSOR_TOPIC = "starswechase/sungai/sensor/data"
MQTT_STATUS_TOPIC = "starswechase/sungai/sensor/status"

BUFFER_SIZE = 5
TURBIDITY_CLEAR_THRESHOLD_V = 2.5

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
            if pulse_time < 0:
                 raise OSError(110, 'Timeout waiting for echo')
            return pulse_time
        except OSError as ex:
            if ex.args[0] == 110:
                raise OSError('Out of range or Echo Error')
            raise ex

    def distance_cm(self):
        try:
            pulse_time = self._send_pulse_and_wait()
            cms = (pulse_time / 2) / 29.1
            if 2 < cms < 400:
                 return cms
            else:
                 return 999
        except OSError:
            return 999
        except Exception as e:
            print(f"HCSR04 Unexpected Error: {e}")
            return 999

def read_dht(dht_sensor):
    for _ in range(3):
        try:
            dht_sensor.measure()
            temp = dht_sensor.temperature()
            hum = dht_sensor.humidity()
            if isinstance(temp, (int, float)) and isinstance(hum, (int, float)) and -20 < temp < 80 and 0 <= hum <= 100:
                return temp, hum
            else:
                print(f"DHT Invalid Reading: Temp={temp}, Hum={hum}")
                time.sleep(2)
        except OSError as e:
            print(f"DHT Read Error: {e}, retrying...")
            time.sleep(2)
        except Exception as e:
            print(f"DHT Unexpected Error: {e}")
            time.sleep(2)
    return None, None

def convert_to_decimal(raw, direction):
    if not isinstance(raw, str) or not raw:
        return None
    try:
        raw_float = float(raw)
        degrees = int(raw_float / 100)
        minutes = raw_float - (degrees * 100)
        decimal = degrees + (minutes / 60.0)
        if direction in ["S", "W"]:
            decimal = -decimal
        return decimal
    except ValueError:
        print(f"GPS Convert Error: Invalid input '{raw}'")
        return None

def parse_gps(nmea_sentence):
    if not nmea_sentence:
        return None, None
    try:
        decoded_sentence = nmea_sentence.decode('ascii', errors='ignore').strip()
        parts = decoded_sentence.split(",")
        if len(parts) < 7:
             return None, None
        if decoded_sentence.startswith('$GPGGA'):
            if parts[6] != '0' and parts[2] and parts[3] and parts[4] and parts[5]:
                lat = convert_to_decimal(parts[2], parts[3])
                lon = convert_to_decimal(parts[4], parts[5])
                if lat is not None and lon is not None:
                   return lat, lon
        elif decoded_sentence.startswith('$GPRMC'):
             if parts[2] == 'A' and parts[3] and parts[4] and parts[5] and parts[6]:
                 lat = convert_to_decimal(parts[3], parts[4])
                 lon = convert_to_decimal(parts[5], parts[6])
                 if lat is not None and lon is not None:
                    return lat, lon
    except IndexError:
        print(f"GPS Parse IndexError: {decoded_sentence}")
    except Exception as e:
        print(f"GPS Parse Error: {e} on sentence: {nmea_sentence}")
    return None, None

def draw_bitmap(oled, bitmap, x_offset=0, y_offset=0):
    if not bitmap or not bitmap[0]: return
    height = len(bitmap)
    width = len(bitmap[0])
    for y in range(height):
        row = bitmap[y]
        for x in range(min(len(row), width)):
            if row[x]:
                if 0 <= (x + x_offset) < oled.width and 0 <= (y + y_offset) < oled.height:
                    oled.pixel(x + x_offset, y + y_offset, 1)

def draw_emote(oled, emote_type):
    oled.fill(0)
    bitmaps = {
        "senyum": [
            [0,0,1,1,1,1,1,1,1,1,1,1,1,0,0,0],[0,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0],[1,1,0,0,1,1,1,1,1,1,1,1,0,0,1,0],[1,1,0,0,1,1,1,1,1,1,1,1,0,0,1,0],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],[1,1,1,0,0,0,0,0,0,0,0,0,1,1,1,0],[1,1,0,1,0,0,0,0,0,0,0,1,0,1,1,0],[1,1,0,0,1,1,1,1,1,1,1,0,0,1,1,0],[1,1,0,0,1,1,1,1,1,1,1,0,0,1,1,0],[1,1,0,1,0,0,0,0,0,0,0,1,0,1,1,0],[1,1,1,0,0,0,0,0,0,0,0,0,1,1,1,0],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
         ],
        "tengkorak": [
             [0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0],[1,1,0,0,0,0,0,0,0,0,0,0,1,1,0,0],[1,0,1,1,1,1,1,1,1,1,1,1,0,1,0,0],[1,0,1,0,0,0,0,0,0,0,0,1,0,1,0,0],[1,0,1,0,1,1,1,1,1,1,0,1,0,1,0,0],[1,0,1,0,1,0,0,0,0,1,0,1,0,1,0,0],[1,0,1,0,1,1,1,1,1,1,0,1,0,1,0,0],[1,0,1,0,0,0,0,0,0,0,0,1,0,1,0,0],[1,0,1,1,1,1,1,1,1,1,1,1,0,1,0,0],[1,1,0,0,0,0,0,0,0,0,0,0,1,1,0,0],[0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0],
         ],
        "gelombang": [
             [0,0,0,0,1,1,0,0,1,1,0,0,1,1,0,0],[0,0,0,1,0,0,1,1,0,0,1,1,0,0,1,0],[0,0,1,0,0,0,0,0,1,0,0,0,0,0,0,1],[0,1,0,0,0,0,0,0,0,1,0,0,0,0,0,0],[1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0],
         ],
        "lari": [
             [0,0,1,1,0,0],[0,1,1,1,1,0],[0,0,1,1,0,0],[1,1,1,1,1,0],[0,0,1,1,1,1],
         ],
        "awan_hujan": [
             [0,0,1,1,1,0,0],[0,1,1,1,1,1,0],[1,1,1,1,1,1,1],[0,0,1,1,1,0,0],[0,0,1,0,1,0,0],[0,1,0,0,0,1,0],[1,0,0,0,0,0,1],
         ],
        "awan_petir": [
             [0,0,1,1,1,0,0],[0,1,1,1,1,1,0],[1,1,1,1,1,1,1],[0,0,1,1,1,0,0],[0,0,0,1,0,0,0],[0,0,1,1,1,0,0],[0,1,1,0,1,1,0],
         ]
    }
    bitmap = bitmaps.get(emote_type, [[0]*8]*8)
    bitmap_height = len(bitmap)
    bitmap_width = len(bitmap[0]) if bitmap_height > 0 else 0
    x_offset = max(0, (oled.width - bitmap_width) // 2)
    y_offset = max(0, (oled.height - bitmap_height) // 2)
    draw_bitmap(oled, bitmap, x_offset=x_offset, y_offset=y_offset)
    oled.show()

def connect_wifi(ssid, password, max_wait_s=15):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connecting to network...')
        wlan.connect(ssid, password)
        start_time = time.ticks_ms()
        while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start_time) < max_wait_s * 1000:
            print('.', end='')
            time.sleep(1)
    if wlan.isconnected():
        print('\nNetwork config:', wlan.ifconfig())
        return wlan
    else:
        print('\nWiFi connection failed!')
        wlan.active(False)
        return None

def connect_mqtt():
    try:
        client = MQTTClient(
            client_id=MQTT_CLIENT_ID,
            server=MQTT_BROKER,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            ssl=True,
            keepalive=60
        )
        client.connect()
        print("MQTT connected")
        client.publish(MQTT_STATUS_TOPIC, "Connected", retain=True)
        return client
    except Exception as e:
        print(f"MQTT connection failed: {e}")
        return None

def publish_mqtt(client, topic, data):
    try:
        json_data = ujson.dumps(data)
        print(f"Publishing to {topic}: {json_data}")
        client.publish(topic, json_data)
        return True
    except Exception as e:
        print(f"Error publishing to MQTT: {e}")
        return False

print("Initializing sensors and peripherals...")
try:
    ultrasonic = HCSR04(trigger_pin=13, echo_pin=12)
    led = Pin(2, Pin.OUT)
    buzzer = PWM(Pin(14))
    buzzer.duty(0)
    buzzer.freq(1000)
    dht_sensor = dht.DHT11(Pin(25))
    raindrop_adc = ADC(Pin(34))
    raindrop_adc.atten(ADC.ATTN_11DB)
    raindrop_adc.width(ADC.WIDTH_10BIT)
    turbidity_adc = ADC(Pin(32))
    turbidity_adc.atten(ADC.ATTN_11DB)
    turbidity_adc.width(ADC.WIDTH_10BIT)
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
    devices = i2c.scan()
    if 0x3C not in devices:
        print("OLED not found at address 0x3C!")
        oled = None
    else:
        print("OLED found at 0x3C.")
        oled = ssd1306.SSD1306_I2C(128, 64, i2c)
        oled.fill(0)
        oled.text("Initializing...", 0, 0)
        oled.show()
    gps_uart = UART(2, baudrate=9600, tx=17, rx=16, timeout=100, timeout_char=50)
    print("Initialization complete.")
except Exception as e:
    print(f"!!! Error during initialization: {e}")
    sys.print_exception(e)
    oled = None

distance_buffer = []
history_max_distance = None
history_min_distance = None
status = "Initializing"
danger_humidity = False
wlan = None
last_distance_valid = True
last_lat, last_lon = None, None
mqtt_client = None

if oled:
    oled.fill(0)
    oled.text("Connecting WiFi", 0, 10)
    oled.show()
wlan = connect_wifi(WIFI_SSID, WIFI_PASSWORD)
if wlan:
    print("WiFi Connected!")
    if oled:
        oled.fill(0)
        oled.text("WiFi Connected!", 0, 0)
        ip = wlan.ifconfig()[0]
        oled.text(ip, 0, 10)
        oled.show()
        time.sleep(3)
    mqtt_client = connect_mqtt()
else:
    print("WiFi Connection Failed.")
    if oled:
        oled.fill(0)
        oled.text("WiFi Failed!", 0, 0)
        oled.show()
        time.sleep(3)

loop_counter = 0
while True:
    loop_counter += 1
    current_loop_start_time = time.ticks_ms()
    print(f"\n--- Loop {loop_counter} Start ---")

    distance = 999
    temperature = None
    humidity = None
    raindrop_raw = 0
    raindrop_percent = 0.0
    turbidity_value = 0
    turbidity_voltage = 0.0
    latitude = None
    longitude = None
    gps_fix_found = False

    try:
        distance = ultrasonic.distance_cm()
        last_distance_valid = (distance != 999)
        print(f" Ultrasonic: {'{:.1f} cm'.format(distance) if last_distance_valid else 'Error'}")

        temperature, humidity = read_dht(dht_sensor)
        print(f" DHT: Temp={temperature}°C, Hum={humidity}%" if temperature is not None else " DHT: Error")

        raindrop_raw_read = raindrop_adc.read()
        raindrop_raw = 1023 - raindrop_raw_read
        raindrop_raw = max(0, min(1023, raindrop_raw))
        raindrop_percent = (raindrop_raw / 1023.0) * 100.0
        print(f" Raindrop: {raindrop_percent:.1f}% (Raw={raindrop_raw_read})")

        turbidity_value = turbidity_adc.read()
        turbidity_voltage = turbidity_value * (3.3 / 1023.0)
        print(f" Turbidity: {turbidity_voltage:.2f}V (Raw={turbidity_value})")

        if gps_uart.any():
            try:
                gps_data = gps_uart.read()
                if gps_data:
                    lines = gps_data.decode('ascii', errors='ignore').strip().split('\n')
                    for line in reversed(lines):
                         if line.startswith(('$GPGGA', '$GPRMC')):
                             lat, lon = parse_gps(line.encode('ascii'))
                             if lat is not None and lon is not None:
                                 latitude = lat
                                 longitude = lon
                                 last_lat, last_lon = latitude, longitude
                                 gps_fix_found = True
                                 print(f" GPS Fix: Lat={latitude:.4f}, Lon={longitude:.4f}")
                                 break
                    if not gps_fix_found:
                         print(" GPS: No valid fix in received data.")
                         latitude, longitude = last_lat, last_lon
            except Exception as e:
                 print(f"GPS data processing error: {e}")
                 latitude, longitude = last_lat, last_lon
        else:
             print(" GPS: No data from UART.")
             latitude, longitude = last_lat, last_lon

        if last_distance_valid:
            if history_max_distance is None or distance > history_max_distance:
                history_max_distance = distance
            if history_min_distance is None or distance < history_min_distance:
                history_min_distance = distance

            current_time_ms = time.ticks_ms()
            if len(distance_buffer) >= BUFFER_SIZE:
                distance_buffer.pop(0)
            distance_buffer.append((current_time_ms, distance))

        delta_per_min = 0.0
        percent_change = 0.0
        danger_banjir = False

        if len(distance_buffer) == BUFFER_SIZE:
            first_entry = distance_buffer[0]
            last_entry = distance_buffer[-1]
            time_diff_ms = time.ticks_diff(last_entry[0], first_entry[0])
            buffer_time_span_min = time_diff_ms / 60000.0 if time_diff_ms > 0 else 0

            if buffer_time_span_min > 0:
                delta_distance = last_entry[1] - first_entry[1]
                delta_per_min_level = -delta_distance / buffer_time_span_min
                delta_per_min = delta_per_min_level
                initial_distance = first_entry[1]
                if initial_distance > 0:
                    percent_change = (-delta_distance / initial_distance) * 100.0
                else:
                    percent_change = 0.0

                threshold_banjir = 5.0 if raindrop_percent > 60 else 2.0
                print(f" Buffer Times (ms): Start={first_entry[0]}, End={last_entry[0]}, Diff={time_diff_ms:.0f}")
                print(f" Buffer Dist (cm): Start={first_entry[1]:.1f}, End={last_entry[1]:.1f}, Delta={delta_distance:.1f}")
                print(f" Time Span: {buffer_time_span_min:.3f} min")
                print(f" Level Change Rate: {delta_per_min:.2f} cm/min, Threshold: {threshold_banjir:.1f}, Rain: {raindrop_percent:.1f}%")

                if delta_per_min > threshold_banjir:
                    status = "Bahaya Banjir!"
                    buzzer.freq(1500)
                    buzzer.duty(512)
                    led.on()
                    danger_banjir = True
                elif delta_per_min < -1.5:
                    status = "Air Menurun"
                    buzzer.duty(0)
                    led.off()
                    danger_banjir = False
                else:
                    status = "Aman"
                    buzzer.duty(0)
                    led.off()
                    danger_banjir = False
            else:
                 status = "Calc Err: Time"
                 print("Calculation Error: Buffer time span <= 0")
                 buzzer.duty(0)
                 led.off()
                 danger_banjir = False
        else:
             if not last_distance_valid:
                 status = "Sensor Error"
             else:
                 status = f"Collecting {len(distance_buffer)}/{BUFFER_SIZE}"
             buzzer.duty(0)
             led.off()
             danger_banjir = False

        danger_humidity = False
        if humidity is not None and humidity >= 90:
             danger_humidity = True
             if not danger_banjir:
                  buzzer.freq(2000)
                  buzzer.duty(300)
        elif not danger_banjir:
             buzzer.duty(0)

        if oled:
            oled.fill(0)
            temp_str = "{:.0f}".format(temperature) if temperature is not None else '--'
            hum_str = "{:.0f}".format(humidity) if humidity is not None else '--'
            oled.text(f"T:{temp_str}C H:{hum_str}%", 0, 0)
            oled.text(f"Rain: {raindrop_percent:.1f}%", 0, 10)
            dist_str = "{:.1f}cm".format(distance) if last_distance_valid else "Error"
            oled.text(f"Dist: {dist_str}", 0, 20)
            oled.text(f"Turb V: {turbidity_voltage:.2f}V", 0, 30)
            if latitude is not None and longitude is not None:
                gps_text = "GPS:{:.2f},{:.2f}".format(latitude, longitude)
                oled.text(gps_text[:16], 0, 40)
            else:
                oled.text("GPS: Waiting...", 0, 40)
            oled.text(status[:16], 0, 50)
            oled.show()
            time.sleep(5)

            if len(distance_buffer) == BUFFER_SIZE:
                oled.fill(0)
                oled.text(f"Status: {status}"[:16], 0, 0)
                oled.text(f"Lvl Chg:{delta_per_min:.1f}cm/m", 0, 10)
                max_d_str = "{:.1f}".format(history_max_distance) if history_max_distance is not None else '--'
                min_d_str = "{:.1f}".format(history_min_distance) if history_min_distance is not None else '--'
                oled.text(f"MaxD:{max_d_str} MinD:{min_d_str}", 0, 20)
                udara_status = "Bahaya!" if danger_humidity else "Normal"
                oled.text(f"Udara: {udara_status}", 0, 30)
                is_clear = turbidity_voltage < TURBIDITY_CLEAR_THRESHOLD_V
                kekeruhan_status = "iya" if is_clear else "tidak"
                oled.text(f"Jernih : {kekeruhan_status}", 0, 40)
                wifi_status = "OK" if wlan and wlan.isconnected() else "DOWN"
                oled.text(f"WiFi: {wifi_status}", 0, 50)
                oled.show()
                time.sleep(5)

            hujan_keras = raindrop_percent > 80
            hujan_biasa = raindrop_percent > 50
            all_safe = not danger_banjir and not danger_humidity and not hujan_biasa
            emote_to_show = "senyum"
            if danger_banjir and danger_humidity:
                emote_to_show = "tengkorak"
            elif danger_banjir:
                emote_to_show = "gelombang"
            elif danger_humidity:
                emote_to_show = "lari"
            elif hujan_keras:
                emote_to_show = "awan_petir"
            elif hujan_biasa:
                emote_to_show = "awan_hujan"
            draw_emote(oled, emote_to_show)
            time.sleep(5)

        payload = {
            "distance": round(distance, 1) if last_distance_valid else None,
            "temperature": temperature,
            "humidity": humidity,
            "raindrop_percent": round(raindrop_percent, 1),
            "turbidity_voltage": round(turbidity_voltage, 2),
            "latitude": latitude,
            "longitude": longitude,
            "delta_per_min": round(delta_per_min, 2) if len(distance_buffer) == BUFFER_SIZE else None,
            "percent_change": round(percent_change, 2) if len(distance_buffer) == BUFFER_SIZE else None,
            "status": status,
            "danger_banjir": danger_banjir,
            "danger_humidity": danger_humidity
        }

        if wlan and wlan.isconnected():
            print("WiFi OK. Checking MQTT...")
            if mqtt_client is None or not mqtt_client.is_connected():
                print("MQTT disconnected. Attempting to reconnect...")
                if oled:
                    oled.fill(0)
                    oled.text("MQTT Lost...", 0, 20)
                    oled.text("Reconnecting...", 0, 30)
                    oled.show()
                mqtt_client = connect_mqtt()
            if mqtt_client:
                print("MQTT OK. Sending data...")
                success = publish_mqtt(mqtt_client, MQTT_SENSOR_TOPIC, payload)
                if success:
                    print("Data sent successfully!")
                    mqtt_client.publish(MQTT_STATUS_TOPIC, "Data Sent", retain=True)
                else:
                    print("Failed to send data.")
                    mqtt_client.publish(MQTT_STATUS_TOPIC, "Error: Send Failed", retain=True)
            else:
                print("MQTT connection failed. Skipping send.")
                if oled:
                    oled.fill(0)
                    oled.text("MQTT Failed!", 0, 20)
                    oled.show()
                    time.sleep(2)
        else:
            print("WiFi disconnected. Attempting to reconnect...")
            led.off()
            buzzer.duty(0)
            if oled:
                oled.fill(0)
                oled.text("WiFi Lost...", 0, 20)
                oled.text("Reconnecting...", 0, 30)
                oled.show()
            wlan = connect_wifi(WIFI_SSID, WIFI_PASSWORD, max_wait_s=10)
            if wlan and wlan.isconnected():
                 print("WiFi Reconnected! MQTT will reconnect next loop.")
                 if oled:
                     oled.fill(0)
                     oled.text("WiFi Reconnected", 0, 20)
                     ip = wlan.ifconfig()[0]
                     oled.text(ip, 0, 30)
                     oled.show()
                     time.sleep(2)
                 mqtt_client = None
            else:
                 print("WiFi Reconnect failed. Skipping send.")
                 if oled:
                     oled.fill(0)
                     oled.text("WiFi Failed!", 0, 20)
                     oled.show()
                     time.sleep(2)

        print("-" * 30)
        print("Summary:")
        print(f" Dist: {'{:.1f} cm'.format(distance) if last_distance_valid else 'Error'}")
        print(f" Temp: {temperature}°C, Hum: {humidity}%" if temperature is not None else " Temp/Hum: Error")
        print(f" Rain: {raindrop_percent:.1f}%")
        print(f" Turb: {turbidity_voltage:.2f}V")
        print(f" GPS: {'{:.4f}, {:.4f}'.format(latitude, longitude) if latitude is not None else '--'}")
        print(f" Rate: {'{:.2f} cm/min'.format(delta_per_min) if len(distance_buffer) == BUFFER_SIZE else 'N/A'}")
        print(f" Status: {status}")
        print(f" Danger Flood: {danger_banjir}, Danger Humid: {danger_humidity}")
        print("-" * 30)

    except Exception as e:
        print(f"!!! An critical error occurred in the main loop: {e}")
        sys.print_exception(e)
        if oled:
             try:
                 oled.fill(0)
                 oled.text("Main Loop Error!", 0, 0)
                 oled.text(str(e)[:16], 0, 10)
                 oled.show()
             except Exception:
                 print("Error updating OLED during exception handling")
        try:
            buzzer.duty(0)
            led.off()
        except Exception:
            print("Error resetting outputs")
        time.sleep(10)

    loop_duration_ms = time.ticks_diff(time.ticks_ms(), current_loop_start_time)
    target_loop_time_ms = (60.0 / BUFFER_SIZE) * 1000.0
    sleep_duration_ms = max(100, target_loop_time_ms - loop_duration_ms)
    print(f"Loop duration: {loop_duration_ms} ms. Sleeping for {sleep_duration_ms:.0f} ms...")
    time.sleep_ms(int(sleep_duration_ms))