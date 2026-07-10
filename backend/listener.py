import paho.mqtt.client as mqtt
import psycopg2
import json
import os
import logging
import time
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'climat_monitor'),
    'user': os.getenv('DB_USER', 'climat'),
    'password': os.getenv('DB_PASSWORD', 'secret')
}

MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'esp32/sensors')
MQTT_USER = os.getenv('MQTT_USER', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')


def insert_sensor_data(device_id, temperature, humidity):
    """Вставка данных в PostgreSQL."""
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        now = datetime.now(timezone.utc)
        cur.execute(
            "INSERT INTO sensor_data (time, device_id, temperature, humidity) VALUES (%s, %s, %s, %s)",
            (now, device_id, temperature, humidity)
        )
        conn.commit()
        logging.info(f"Data inserted: {device_id}, Temp: {temperature}, Hum: {humidity}")
    except Exception as e:
        logging.error(f"DB error: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def on_message(client, userdata, msg):
    logging.info(f"Message received on topic {msg.topic}: {msg.payload.decode()}")
    try:
        payload = json.loads(msg.payload.decode())
        device_id = payload.get('device')
        temperature = payload.get('temperature')
        humidity = payload.get('humidity')

        if device_id is None:
            logging.warning("Missing 'device' in payload")
            return
        if temperature is None or humidity is None:
            logging.warning("Missing 'temperature' or 'humidity' in payload")
            return

        insert_sensor_data(device_id, temperature, humidity)
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON payload")
    except Exception as e:
        logging.error(f"Error processing message: {e}")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker")
        # подписываемся заново при каждом успешном подключении
        client.subscribe(MQTT_TOPIC)
        logging.info(f"Subscribed to {MQTT_TOPIC}")
    else:
        logging.error(f"Connection failed, rc={rc}")


def on_disconnect(client, userdata, rc):
    logging.warning(f"Disconnected (rc={rc}). Reconnecting...")
    while True:
        try:
            client.reconnect()
            logging.info("Reconnected successfully")
            break
        except Exception as e:
            logging.error(f"Reconnect attempt failed: {e}")
            time.sleep(5)


def main():
    client = mqtt.Client()
    if MQTT_USER and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    logging.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT} with user={MQTT_USER}")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    client.loop_forever()


if __name__ == "__main__":
    main()