import json
import os
from datetime import datetime, timedelta
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

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))


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

        cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                time        TIMESTAMPTZ NOT NULL,
                device_id   TEXT NOT NULL,
                temperature DOUBLE PRECISION,
                humidity    DOUBLE PRECISION,
                PRIMARY KEY (time, device_id)
            );
        """)

        cur.execute("""
            SELECT create_hypertable('sensor_data', 'time',
                   if_not_exists => TRUE, migrate_data => TRUE);
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_device_time
            ON sensor_data (device_id, time DESC);
        """)

        cur.execute("""
            ALTER TABLE sensor_data SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'device_id'
            );
        """)

        cur.execute("""
            SELECT add_compression_policy('sensor_data', INTERVAL '7 days',
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


# ---------- REST API ----------

@app.route('/api/data', methods=['GET'])
def get_all_data():
    # ИЗМЕНЕНО: дефолтное устройство теперь esp32_1
    period = request.args.get('period', '1h')
    device = request.args.get('device', 'esp32_1')

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

        if period in ('7d', '30d', 'all'):
            if start_time:
                cur.execute("""
                    SELECT
                        time_bucket('1 day', time) AS day,
                        AVG(temperature) AS temperature,
                        AVG(humidity) AS humidity
                    FROM sensor_data
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
                    FROM sensor_data
                    WHERE device_id = %s
                    GROUP BY day
                    ORDER BY day ASC
                """, (device,))
            rows = cur.fetchall()
            data = [
                {
                    "timestamp": row["day"].isoformat(),
                    "temperature": round(row["temperature"], 2) if row["temperature"] is not None else None,
                    "humidity": round(row["humidity"], 2) if row["humidity"] is not None else None
                }
                for row in rows
            ]
        else:
            if start_time:
                cur.execute("""
                    SELECT time, temperature, humidity
                    FROM sensor_data
                    WHERE device_id = %s AND time >= %s
                    ORDER BY time ASC
                """, (device, start_time))
            else:
                cur.execute("""
                    SELECT time, temperature, humidity
                    FROM sensor_data
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
    # ИЗМЕНЕНО: убрана фильтрация по device_id, теперь возвращается последняя запись без привязки
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT time, device_id, temperature, humidity
            FROM sensor_data
            ORDER BY time DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return jsonify({
                "success": True,
                "data": {
                    "timestamp": row["time"].isoformat(),
                    "device_id": row["device_id"],
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
    # ИЗМЕНЕНО: убрано условие WHERE device_id, теперь статистика по всем устройствам
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                COUNT(*) AS total_readings,
                AVG(temperature) AS avg_temp,
                AVG(humidity) AS avg_hum,
                MIN(temperature) AS min_temp,
                MAX(temperature) AS max_temp,
                MIN(humidity) AS min_hum,
                MAX(humidity) AS max_hum
            FROM sensor_data
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


@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sensor_data');")
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
    if filename.startswith('api/'):
        return '', 404
    return send_from_directory(FRONTEND_DIR, filename)


if __name__ == '__main__':
    init_db()
    print("🚀 Flask API server running on port 8000")
    app.run(host='0.0.0.0', port=8000, debug=False)