#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include "esp_timer.h"
#include "img_converters.h"
#include "Arduino.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include <PubSubClient.h>
#include <base64.h>

const char* ssid = "Yoru no Hajimarisa";
const char* password = "bunnygirl";

const char* mqtt_broker = "f6edeb4adb7c402ca7291dd7ef4d8fc5.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char* mqtt_user = "hivemq.webclient.1747043871321";
const char* mqtt_password = "ab45PjNdISi;Bf9>2,G#";
const char* client_id = "ESP32_Camera_001";

const char* image_topic = "starswechase/sungai/cv/camera/image_base64";
const char* status_topic = "starswechase/sungai/cv/camera/status";

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#define LED_FLASH_PIN 4

WiFiClientSecure espClient;
PubSubClient client(espClient);

unsigned long lastCaptureTime = 0;
const unsigned long captureInterval = 5000;

void setup_wifi() {
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  byte wifi_conn = 0;
  while (WiFi.status() != WL_CONNECTED && wifi_conn < 30) {
    delay(500);
    Serial.print(".");
    wifi_conn++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi connection failed! Rebooting...");
    delay(5000);
    ESP.restart();
  }
  Serial.println("");
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect(client_id, mqtt_user, mqtt_password)) {
      Serial.println("connected");
      client.publish(status_topic, "Idle", true);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 20;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_QCIF;
    config.jpeg_quality = 20;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return false;
  }

  sensor_t *s = esp_camera_sensor_get();
  s->set_vflip(s, 0);
  s->set_hmirror(s, 0);
  s->set_brightness(s, 0);
  s->set_contrast(s, 0);
  s->set_saturation(s, 0);

  return true;
}

void captureAndSend() {
  client.publish(status_topic, "Capturing...", true);
  Serial.println("Capturing photo...");
  digitalWrite(LED_FLASH_PIN, HIGH);
  delay(200);

  camera_fb_t *fb = esp_camera_fb_get();
  digitalWrite(LED_FLASH_PIN, LOW);

  if (!fb) {
    Serial.println("Camera capture failed");
    client.publish(status_topic, "Error: Capture Failed", true);
    return;
  }

  client.publish(status_topic, "Encoding...", true);
  Serial.println("Encoding image to Base64...");

  String encoded = base64::encode(fb->buf, fb->len);
  esp_camera_fb_return(fb);

  client.publish(status_topic, "Sending...", true);
  Serial.printf("Image size: %d bytes, Base64 size: %d bytes\n", fb->len, encoded.length());
  Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
  Serial.printf("MQTT state: %d\n", client.state());

  if (client.connected()) {
    Serial.printf("Publishing to %s, length: %d\n", image_topic, encoded.length());
    bool sent = client.publish(image_topic, encoded.c_str(), false);
    if (sent) {
      Serial.println("Image sent successfully");
      client.publish(status_topic, "Idle", true);
    } else {
      Serial.println("Failed to send image");
      client.publish(status_topic, "Error: Send Failed", true);
    }
  } else {
    Serial.println("MQTT not connected, skipping publish");
    client.publish(status_topic, "Error: Send Failed", true);
  }
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println("\nStarting ESP32-CAM MQTT Publisher...");

  pinMode(LED_FLASH_PIN, OUTPUT);
  digitalWrite(LED_FLASH_PIN, LOW);

  if (!initCamera()) {
    Serial.println("Failed to init camera. Rebooting...");
    delay(5000);
    ESP.restart();
  }

  setup_wifi();

  espClient.setInsecure();
  client.setServer(mqtt_broker, mqtt_port);
  client.setBufferSize(16384);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long currentTime = millis();
  if (currentTime - lastCaptureTime >= captureInterval) {
    lastCaptureTime = currentTime;
    captureAndSend();
  }

  delay(100);
}