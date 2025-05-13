from flask import Flask, request, jsonify
from pymongo import MongoClient, errors as pymongo_errors
import paho.mqtt.client as mqtt
from datetime import datetime
import base64
from io import BytesIO
from PIL import Image
import logging
from math import radians, sin, cos, sqrt, atan2
from bson import ObjectId

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(name)s:%(message)s')

MONGO_URI = "mongodb+srv://rifqiraehan86:NAGPGR8yKvVpLjsT@cluster0.lkusi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "SIC6"
MONITORING_COLLECTION_NAME = "RiverMonitoring"
RIVER_COLLECTION_NAME = "River"
IMAGE_COLLECTION_NAME = "CameraImages"

MQTT_BROKER = "f6edeb4adb7c402ca7291dd7ef4d8fc5.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1747043871321"
MQTT_PASS = "ab45PjNdISi;Bf9>2,G#"
IMAGE_TOPIC = "starswechase/sungai/cv/camera/image_base64"

client = None
db = None
monitoring_collection = None
river_collection = None
image_collection = None

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000, connectTimeoutMS=20000, socketTimeoutMS=20000)
    client.admin.command('ping')
    logging.info("MongoDB connection successful!")
    db = client[DB_NAME]
    monitoring_collection = db[MONITORING_COLLECTION_NAME]
    river_collection = db[RIVER_COLLECTION_NAME]
    image_collection = db[IMAGE_COLLECTION_NAME]
except pymongo_errors.ConnectionFailure as e:
    logging.error(f"Could not connect to MongoDB: {e}", exc_info=True)
except Exception as e:
    logging.error(f"An unexpected error occurred during MongoDB setup: {e}", exc_info=True)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker")
        client.subscribe(IMAGE_TOPIC)
    else:
        logging.error(f"Failed to connect to MQTT broker, return code {rc}")

def on_message(client, userdata, msg):
    try:
        logging.info(f"Received message on {msg.topic}")
        encoded_image = msg.payload.decode('utf-8')
        img_data = base64.b64decode(encoded_image)
        img = Image.open(BytesIO(img_data))

        image_doc = {
            "timestamp": datetime.now(),
            "river_id": "",
            "image_data": img_data,
            "format": img.format,
            "size": img.size
        }
        image_collection.insert_one(image_doc)
        logging.info("Image saved to MongoDB")
    except Exception as e:
        logging.error(f"Error processing MQTT message: {e}")

mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.tls_set()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    logging.error(f"Failed to connect to MQTT broker: {e}")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    try:
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    except (ValueError, TypeError):
        app.logger.warning(f"Invalid input for haversine calculation: {(lat1, lon1, lat2, lon2)}")
        return float('inf')

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c * 1000
    return distance

@app.route("/sensor", methods=["POST"])
def receive_sensor_data():
    if monitoring_collection is None or river_collection is None:
        app.logger.error("MongoDB collections are not available (failed during startup). Cannot process request.")
        return jsonify({"error": "Database connection error - check server logs"}), 500

    data = request.get_json()

    if not data:
        app.logger.warning("Received empty or non-JSON payload.")
        return jsonify({"error": "Invalid data: No valid JSON payload received"}), 400

    app.logger.info(f"Received data payload: {data}")

    try:
        required_fields = ["status", "danger_banjir", "danger_humidity"]
        missing_fields = [field for field in required_fields if data.get(field) is None]
        if missing_fields:
             app.logger.warning(f"Received data missing essential fields: {', '.join(missing_fields)}. Payload: {data}")
             return jsonify({"error": f"Invalid data: Missing essential fields ({', '.join(missing_fields)})"}), 400

        received_status = data["status"]
        danger_banjir = data["danger_banjir"]
        danger_humidity = data["danger_humidity"]
        latitude_raw = data.get("latitude")
        longitude_raw = data.get("longitude")
        turbidity_voltage_raw = data.get("turbidity_voltage")
        delta_per_min_raw = data.get("delta_per_min")

        final_status = received_status
        if delta_per_min_raw is None and isinstance(received_status, str) and "Collecting" in received_status:
            final_status = "Aman"
            app.logger.info(f"Overriding status '{received_status}' to 'Aman' because delta_per_min is None.")
        elif delta_per_min_raw is None:
             app.logger.warning(f"delta_per_min is None, but status is '{received_status}'. Keeping received status.")

        sensor_latitude = None
        sensor_longitude = None
        turbidity_voltage = None

        if latitude_raw is not None:
            try: sensor_latitude = float(latitude_raw)
            except (ValueError, TypeError): app.logger.warning(f"Invalid latitude value, cannot convert to float: {latitude_raw}")
        if longitude_raw is not None:
            try: sensor_longitude = float(longitude_raw)
            except (ValueError, TypeError): app.logger.warning(f"Invalid longitude value, cannot convert to float: {longitude_raw}")
        if turbidity_voltage_raw is not None:
            try: turbidity_voltage = float(turbidity_voltage_raw)
            except (ValueError, TypeError): app.logger.warning(f"Invalid turbidity_voltage value, cannot convert to float: {turbidity_voltage_raw}")

        closest_river_id = None
        assigned_river_name = "N/A"
        min_distance_meters = None

        if sensor_latitude is not None and sensor_longitude is not None:
            try:
                rivers = list(river_collection.find({"latitude": {"$exists": True, "$ne": None}, "longitude": {"$exists": True, "$ne": None}}))
                if rivers:
                    min_distance = float('inf')
                    for river in rivers:
                        river_lat_str = river.get("latitude")
                        river_lon_str = river.get("longitude")
                        if river_lat_str and river_lon_str:
                            distance = haversine(sensor_latitude, sensor_longitude, river_lat_str, river_lon_str)
                            if distance < min_distance:
                                min_distance = distance
                                closest_river_id = river["_id"]
                                assigned_river_name = river.get("nama", "Unknown River")
                    min_distance_meters = min_distance if min_distance != float('inf') else None
                    app.logger.info(f"Closest river found: {assigned_river_name} (ID: {closest_river_id}) at distance {min_distance_meters:.1f}m")
                else:
                    app.logger.warning("No rivers with coordinates found in the database to compare distance.")
            except Exception as geo_e:
                 app.logger.error(f"Error during closest river calculation: {geo_e}", exc_info=True)

        else:
            app.logger.info("Sensor coordinates not provided, attempting to assign default river 'Sungai Keputih Tegal Timur'.")
            try:
                keputih = river_collection.find_one({"nama": "Sungai Keputih Tegal Timur"})
                if keputih:
                    closest_river_id = keputih["_id"]
                    assigned_river_name = keputih.get("nama")
                    app.logger.info(f"Assigned default river: {assigned_river_name} (ID: {closest_river_id})")
                else:
                     app.logger.warning("Default river 'Sungai Keputih Tegal Timur' not found.")
            except Exception as default_e:
                app.logger.error(f"Error finding default river: {default_e}", exc_info=True)

        sensor_data = {
            "timestamp": datetime.now(),
            "distance": data.get("distance"),
            "temperature": data.get("temperature"),
            "humidity": data.get("humidity"),
            "raindrop_percent": data.get("raindrop_percent"),
            "turbidity_voltage": turbidity_voltage,
            "latitude": sensor_latitude,
            "longitude": sensor_longitude,
            "delta_per_min": data.get("delta_per_min"),
            "percent_change": data.get("percent_change"),
            "status": final_status,
            "danger_banjir": danger_banjir,
            "danger_humidity": danger_humidity,
            "sungai_id": closest_river_id
        }

        sensor_data_cleaned = {k: v for k, v in sensor_data.items() if v is not None}

        insert_result = monitoring_collection.insert_one(sensor_data_cleaned)
        app.logger.info(f"Data saved successfully for river '{assigned_river_name}' with ID: {insert_result.inserted_id}")
        return jsonify({"message": "Data received and saved", "id": str(insert_result.inserted_id), "assigned_river": assigned_river_name}), 200

    except KeyError as ke:
        app.logger.error(f"Missing key in received JSON data: {ke}. Payload: {data}", exc_info=True)
        return jsonify({"error": f"Invalid data: Missing key '{ke}'"}), 400
    except pymongo_errors.PyMongoError as pe:
        app.logger.error(f"MongoDB Error during insert: {pe}", exc_info=True)
        return jsonify({"error": f"Database insert error: {pe}"}), 500
    except Exception as e:
        app.logger.error(f"Error processing request: {e}", exc_info=True)
        return jsonify({"error": f"An internal server error occurred: {str(e)}"}), 500

@app.route('/')
def index():
    return "Flask MQTT Subscriber and Sensor Receiver is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)