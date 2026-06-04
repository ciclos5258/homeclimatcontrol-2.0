import json
import os
import threading
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import psycopg2
import psycopg2.extras

app = Flask(__name__)
CORS(app)

# ---------- Конфигурация БД ----------
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://climat:secret@localhost:5432/climat_monitor'
)

# ---------- Конфигурация MQTT ----------
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
MQTT_TOPIC = os.environ.get('MQTT_TOPIC', 'esp32/sensors')

FRONTEND_DIR = '/frontend'

def get_db_connection():
    """Создаёт и возвращает новое подключение к PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    """Инициализирует базу данных: создаёт расширение TimescaleDB и таблицу."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Включаем расширение TimescaleDB (если ещё не включено)
        cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

        # Создаём таблицу с составным первичным ключом (время + устройство)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                time        TIMESTAMPTZ NOT NULL,
                device_id   TEXT NOT NULL,
                temperature DOUBLE PRECISION,
                humidity    DOUBLE PRECISION,
                PRIMARY KEY (time, device_id)
            );
        """)

        # Превращаем обычную таблицу в гипертаблицу TimescaleDB
        cur.execute("""
            SELECT create_hypertable('sensor_readings', 'time',
                   if_not_exists => TRUE, migrate_data => TRUE);
        """)

        # Создаём индекс для быстрого получения последних данных
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_device_time
            ON sensor_readings (device_id, time DESC);
        """)

        # Включаем сжатие старых данных
        cur.execute("""
            ALTER TABLE sensor_readings SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'device_id'
            );
        """)

        # Автоматически сжимать чанки старше 7 дней (политика)
        cur.execute("""
            SELECT add_compression_policy('sensor_readings', INTERVAL '7 days',
                   if_not_exists => TRUE);
        """)

        conn.commit()
        print("✅ База данных инициализирована (PostgreSQL + TimescaleDB)")
    except Exception as e:
        print("❌ Ошибка при инициализации БД:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def save_reading(timestamp, temperature, humidity, device_id="esp32_main"):
    """Сохраняет одно измерение в БД."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sensor_readings (time, device_id, temperature, humidity)
            VALUES (%s, %s, %s, %s)
        """, (timestamp, device_id, temperature, humidity))
        conn.commit()
    except Exception as e:
        print("❌ Ошибка сохранения:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# ---------- MQTT обработчики ----------
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"📡 MQTT подключён, код: {reason_code}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        temp = float(payload["temperature"])
        hum = float(payload["humidity"])
        # Используем текущее UTC время
        timestamp = datetime.utcnow()
        save_reading(timestamp, temp, hum)
        print(f"💾 Сохранено: {timestamp}, {temp}°C, {hum}%")
    except Exception as e:
        print("❌ Ошибка обработки MQTT:", e)

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.username_pw_set("python", "pythonpassword")
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# ---------- REST API ----------
@app.route('/api/data', methods=['GET'])
def get_all_data():
    period = request.args.get('period', '1h')
    device = request.args.get('device', 'esp32_main')
    
    now = datetime.utcnow()
    if period == '1h':
        start_time = now - timedelta(hours=1)
    elif period == '6h':
        start_time = now - timedelta(hours=6)
    elif period == '24h':
        start_time = now - timedelta(days=1)
    elif period == '7d':
        start_time = now - timedelta(days=7)
    elif period == '30d':
        start_time = now - timedelta(days=30)
    else:
        start_time = None  # 'all'

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Для длинных периодов используем агрегацию по дням
        if period in ('7d', '30d', 'all'):
            if start_time:
                cur.execute("""
                    SELECT
                        time_bucket('1 day', time) AS day,
                        AVG(temperature) AS temperature,
                        AVG(humidity) AS humidity
                    FROM sensor_readings
                    WHERE device_id = %s AND time >= %s
                    GROUP BY day
                    ORDER BY day ASC
                """, (device, start_time))
            else:
                cur.execute("""
                    SELECT
                        time_bucket('1 day', time) AS day,
                        AVG(temperature) AS temperature,
                        AVG(humidity) AS humidity
                    FROM sensor_readings
                    WHERE device_id = %s
                    GROUP BY day
                    ORDER BY day ASC
                """, (device,))
            rows = cur.fetchall()
            # Приводим к единому формату: timestamp, temperature, humidity
            data = [
                {
                    "timestamp": row["day"].isoformat(),
                    "temperature": round(row["temperature"], 2) if row["temperature"] is not None else None,
                    "humidity": round(row["humidity"], 2) if row["humidity"] is not None else None
                }
                for row in rows
            ]
        else:
            # Сырые данные для коротких периодов
            if start_time:
                cur.execute("""
                    SELECT time, temperature, humidity
                    FROM sensor_readings
                    WHERE device_id = %s AND time >= %s
                    ORDER BY time ASC
                """, (device, start_time))
            else:
                cur.execute("""
                    SELECT time, temperature, humidity
                    FROM sensor_readings
                    WHERE device_id = %s
                    ORDER BY time ASC
                """, (device,))
            rows = cur.fetchall()
            data = [
                {
                    "timestamp": row["time"].isoformat(),
                    "temperature": row["temperature"],
                    "humidity": row["humidity"]
                }
                for row in rows
            ]

        return jsonify({
            "success": True,
            "data": data,
            "count": len(data)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/latest', methods=['GET'])
def get_latest():
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT time, temperature, humidity
            FROM sensor_readings
            WHERE device_id = 'esp32_main'
            ORDER BY time DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return jsonify({
                "success": True,
                "data": {
                    "timestamp": row["time"].isoformat(),
                    "temperature": row["temperature"],
                    "humidity": row["humidity"]
                }
            })
        return jsonify({"success": False, "error": "Нет данных"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Общая статистика по всем данным (без временных рамок)
        cur.execute("""
            SELECT
                COUNT(*) AS total_readings,
                AVG(temperature) AS avg_temp,
                AVG(humidity) AS avg_hum,
                MIN(temperature) AS min_temp,
                MAX(temperature) AS max_temp,
                MIN(humidity) AS min_hum,
                MAX(humidity) AS max_hum
            FROM sensor_readings
            WHERE device_id = 'esp32_main'
        """)
        row = cur.fetchone()
        if row and row["total_readings"] > 0:
            stats = {
                "total_readings": row["total_readings"],
                "avg_temperature": round(row["avg_temp"], 1),
                "avg_humidity": round(row["avg_hum"], 1),
                "min_temperature": row["min_temp"],
                "max_temperature": row["max_temp"],
                "min_humidity": row["min_hum"],
                "max_humidity": row["max_hum"]
            }
        else:
            stats = {"total_readings": 0}

        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

def start_mqtt():
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_forever()

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверяет готовность БД и наличие таблицы."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sensor_readings');")
        exists = cur.fetchone()[0]
        cur.close()
        conn.close()
        if exists:
            return jsonify({"status": "healthy", "database": "ok", "table": "exists"})
        else:
            return jsonify({"status": "degraded", "table": "missing"}), 503
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/')
def serve_frontend_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_frontend_assets(filename):
    """Все остальные файлы (CSS, JS, изображения)"""
    # Не мешаем API-вызовам
    if filename.startswith('api/'):
        return '', 404
    return send_from_directory(FRONTEND_DIR, filename)

if __name__ == '__main__':
    init_db()
    threading.Thread(target=start_mqtt, daemon=True).start()
    print("🚀 Flask API server running on port 5002")
    app.run(host='0.0.0.0', port=5002, debug=False)