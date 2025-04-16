from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

uri = "mongodb+srv://rifqiraehan86:NAGPGR8yKvVpLjsT@cluster0.lkusi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(uri)
db = client.SIC6
collection = db.RiverMonitoring2

@app.route("/sensor", methods=["POST"])
def receive_sensor_data():
    try:
        data = request.get_json()
        if data and all(key in data for key in ("distance", "warning", "temperature", "humidity", "raindrop")):
            distance = data["distance"]
            warning = data["warning"]
            temperature = data["temperature"]
            humidity = data["humidity"]
            raindrop = data["raindrop"]
            timestamp = datetime.now()
            sensor_data = {
                "distance": distance,
                "warning": warning,
                "temperature": temperature,
                "humidity": humidity,
                "raindrop": raindrop,
                "timestamp": timestamp
            }
            collection.insert_one(sensor_data)
            return jsonify({"message": "Data received and saved to MongoDB"}), 200
        else:
            return jsonify({"error": "Invalid data: Missing required fields (distance, warning, temperature, humidity, raindrop)"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)