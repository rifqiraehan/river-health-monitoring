from flask import Flask, request, jsonify
from pymongo import MongoClient, errors as pymongo_errors
from datetime import datetime
import logging
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

uri = "mongodb+srv://rifqiraehan86:NAGPGR8yKvVpLjsT@cluster0.lkusi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "SIC6"
COLLECTION_NAME = "RiverMonitoring"
RIVER_COLLECTION_NAME = "River"

client = None
db = None
monitoring_collection = None
river_collection = None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of the Earth in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c * 1000 # Convert to meters
    return distance

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=10000)
    client.admin.command('ping')
    print("MongoDB connection successful!")
    db = client[DB_NAME]
    monitoring_collection = db[COLLECTION_NAME]
    river_collection = db[RIVER_COLLECTION_NAME]
except pymongo_errors.ConnectionFailure as e:
    logging.error(f"Could not connect to MongoDB: {e}")
except Exception as e:
    logging.error(f"An unexpected error occurred during MongoDB setup: {e}")

@app.route("/sensor", methods=["POST"])
def receive_sensor_data():
    if monitoring_collection is None or river_collection is None:
        app.logger.error("MongoDB collections are not available (failed during startup).")
        return jsonify({"error": "Database connection error - check server logs"}), 500

    data = request.get_json()

    if not data:
        app.logger.warning("Received empty JSON payload.")
        return jsonify({"error": "Invalid data: No JSON payload received"}), 400

    try:
        status = data.get("status")
        danger_banjir = data.get("danger_banjir")
        danger_humidity = data.get("danger_humidity")
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if status is None or danger_banjir is None or danger_humidity is None:
            app.logger.warning(f"Received data missing essential fields: {data}")
            return jsonify({"error": "Invalid data: Missing essential status fields (status, danger_banjir, danger_humidity)"}), 400

        sensor_latitude = None
        sensor_longitude = None

        if isinstance(latitude, str) and latitude.strip():
            try:
                sensor_latitude = float(latitude)
            except ValueError:
                app.logger.warning(f"Invalid latitude value: {latitude}")
        elif isinstance(latitude, (int, float)):
            sensor_latitude = float(latitude)

        if isinstance(longitude, str) and longitude.strip():
            try:
                sensor_longitude = float(longitude)
            except ValueError:
                app.logger.warning(f"Invalid longitude value: {longitude}")
        elif isinstance(longitude, (int, float)):
            sensor_longitude = float(longitude)

        closest_river_id = None
        if sensor_latitude is not None and sensor_longitude is not None:
            rivers = list(river_collection.find({}))
            min_distance = float('inf')
            for river in rivers:
                river_lat = float(river.get("latitude"))
                river_lon = float(river.get("longitude"))
                distance = haversine(sensor_latitude, sensor_longitude, river_lat, river_lon)
                if distance < min_distance:
                    min_distance = distance
                    closest_river_id = river["_id"]
        else:
            keputih = river_collection.find_one({"nama": "Sungai Keputih Tegal Timur"})
            if keputih:
                closest_river_id = keputih["_id"]

        sensor_data = {
            "timestamp": datetime.now(),
            "distance": data.get("distance"),
            "temperature": data.get("temperature"),
            "humidity": data.get("humidity"),
            "raindrop": data.get("raindrop"),
            "latitude": latitude,
            "longitude": longitude,
            "delta_per_min": data.get("delta_per_min"),
            "percent_change": data.get("percent_change"),
            "status": status,
            "danger_banjir": danger_banjir,
            "danger_humidity": danger_humidity,
            "sungai_id": closest_river_id
        }

        insert_result = monitoring_collection.insert_one(sensor_data)
        app.logger.info(f"Data saved successfully with ID: {insert_result.inserted_id}")
        return jsonify({"message": "Data received and saved to MongoDB", "id": str(insert_result.inserted_id)}), 200

    except pymongo_errors.PyMongoError as pe:
        app.logger.error(f"MongoDB Error during insert: {pe}", exc_info=True)
        return jsonify({"error": f"Database insert error: {pe}"}), 500
    except Exception as e:
        app.logger.error(f"Error processing request: {e}", exc_info=True)
        return jsonify({"error": f"An internal server error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)