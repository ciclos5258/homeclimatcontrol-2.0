[Документация на русском](readme_ru.md)

# 🌡️ Climat Monitor — IoT Climate Monitoring System (Docker + TimescaleDB)

A production-grade IoT system for remote temperature and humidity monitoring.  
The ESP32 microcontroller (DHT22) publishes data via MQTT; a separate MQTT listener stores readings in TimescaleDB (PostgreSQL extension). The Flask backend exposes a REST API and serves the web frontend that visualises historical data using Chart.js. All components are containerised with Docker Compose V2.

**Stack:**
- **Backend:** Python (Flask, Gunicorn)
- **MQTT Listener:** Python (paho-mqtt, psycopg2) — runs as a dedicated container
- **Database:** TimescaleDB (PostgreSQL 16)
- **MQTT Broker:** Mosquitto (running on host machine)
- **Proxy:** Nginx (Docker internal + host system for HTTPS termination, Let's Encrypt)
- **Frontend:** JavaScript (native), HTML5, Chart.js
- **Orchestration:** Docker Compose V2, BuildKit

---

## 📁 Project Structure

```text
homeclimatcontrol-2.0/
├── backend/
│   ├── server.py               # Flask REST API
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── app.js                  # main logic + tab switching + live data
│   └── chart.js                # chart initialisation (history tab)
├── nginx/
│   └── nginx.conf              # internal Docker Nginx config (reverse proxy to web)
├── init-db/
│   └── 01-init.sql             # SQL script to create tables (auto-executed on first start)
├── docker-compose.yml
├── Dockerfile                  # for climat_web (Flask + Gunicorn)
├── Dockerfile.listener         # for climat_mqtt_listener
├── listener.py                 # MQTT listener script (with auto-reconnect)
└── .dockerignore
```

---

## 🚀 Features

- 📡 **MQTT ingestion** – dedicated container subscribes to `esp32/sensors` topic and stores every reading
- 💾 **TimescaleDB** – automatic compression of chunks older than 7 days, hypertables for fast time-series queries
- 📊 **REST API** – raw data, latest value, aggregated statistics (avg/min/max) and time-bucketed data (hour/day)
- 📈 **Web dashboard** – interactive Chart.js graph with selectable time periods (1h, 6h, 24h, 7d, 30d, all)
- 🐳 **Full containerisation** – backend, listener, database and internal proxy run in Docker; volumes for persistent storage
- 🔒 **Nginx reverse proxy** – host Nginx terminates HTTPS (Let's Encrypt) and forwards to internal Docker Nginx
- ⚙️ **Environment-based configuration** – all settings via `docker-compose.yml` (can be extended with `.env`)
- 🔄 **Auto-reconnect MQTT listener** – survives temporary network drops

---

## 🔧 Architecture (current version)

```text
ESP32 + DHT22
     │
     ▼ (MQTT, topic esp32/sensors)
┌─────────────┐
│  Mosquitto  │ (host machine)
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│ climat_mqtt_listener │ (Docker container)
│ subscribes & writes  │
└──────────┬───────────┘
           │ (psycopg2)
           ▼
┌──────────────────┐
│  climat_db       │ (TimescaleDB container)
│  table sensor_data (device_id) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ climat_web       │ (Flask + Gunicorn container)
│ REST API + static│
└────────┬─────────┘
         │ http://climat_web:8000
         ▼
┌──────────────────┐
│ climat_nginx     │ (internal Docker Nginx)
│ reverse proxy    │ 127.0.0.1:8080:80
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Host Nginx       │ (system Nginx)
│ HTTPS :443 →     │
│ 127.0.0.1:8080   │
└────────┬─────────┘
         │
         ▼
   Web browser (user)
```

**Key points:**

- All containers are on a dedicated bridge network `app-network`.
- `climat_db` is not exposed to the host; only `climat_web` and `climat_mqtt_listener` connect internally.
- Host Mosquitto must be reachable from the listener container (using host's Docker gateway IP or `extra_hosts`).
- Internal `climat_nginx` uses a dynamic upstream with `resolver 127.0.0.11` to avoid startup failures when `web` isn't ready.
- The database column for device identifier is `device_id` (formerly documented as `sensor_id`).

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/latest` | Most recent reading (any device) |
| `GET` | `/api/stats` | Overall statistics (all devices) |
| `GET` | `/api/data?period=1h&device=esp32_1` | Time-bucketed data (raw for short periods, daily averages for long periods) |
| `GET` | `/api/health` | Health check (database connectivity) |

### Query parameters for `/api/data`

- `period` – `1h`, `6h`, `24h`, `7d`, `30d`, `all`
- `device` – device ID (default: `esp32_1`)

---

## 📊 Web Interface

- **Overview tab** – current temperature/humidity with trend indicators, live status
- **History tab** – Chart.js graph with selectable period, zoom and hover
- **Statistics tab** – aggregated stats for today/week/month
- **Settings tab** – threshold configuration, Telegram notifications
- **Responsive design** – works on desktop and mobile
- **Auto-refresh** – data updates every 3 seconds via `/api/latest`

---

## 🐳 Running with Docker Compose (production)

### Prerequisites

- Ubuntu 24.04+ (or any Linux with Docker Engine 24+)
- Docker Compose Plugin (`docker compose` command, not legacy `docker-compose`)
- Mosquitto MQTT broker **installed on the host** (not in a container)
- Git, curl, and a domain name with DNS pointing to your server (for HTTPS)

### 1. Clone the repository

```bash
git clone https://github.com/ciclos5258/homeclimatcontrol-2.0.git
cd homeclimatcontrol-2.0
```

### 2. Configure environment variables

Settings are defined directly in `docker-compose.yml` (services → environment).

You can override them using an `.env` file:

```env
DATABASE_URL=postgresql://climat:secret@db:5432/climat_monitor
MQTT_BROKER=172.17.0.1
MQTT_PORT=1883
MQTT_TOPIC=esp32/sensors
MQTT_USER=climat
MQTT_PASSWORD=password
```

### 3. Ensure MQTT broker accepts Docker connections

```conf
listener 1883 0.0.0.0
allow_anonymous false
password_file /etc/mosquitto/passwd
```

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd climat
sudo systemctl restart mosquitto
```

### 4. Build and run

```bash
docker compose up -d --build
```

```bash
docker compose logs -f
```

### 5. Configure host Nginx

```nginx
server {
    listen 443 ssl;
    server_name homeclimatcontrol.ru www.homeclimatcontrol.ru;

    ssl_certificate /etc/letsencrypt/live/homeclimatcontrol.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/homeclimatcontrol.ru/privkey.pem;

    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name homeclimatcontrol.ru www.homeclimatcontrol.ru;
    return 301 https://$host$request_uri;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/homeclimatcontrol.ru /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Update firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 1883/tcp
sudo ufw enable
```

---

## 🔐 Security

- MQTT authentication
- Database isolated inside Docker network
- Secrets stored in `.env` or Compose configuration
- Restricted CORS
- HTTPS terminated by host Nginx

---

## 🧪 Local Development

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgresql://climat:secret@localhost:5432/climat_monitor
export MQTT_BROKER=localhost
export MQTT_PORT=1883
export MQTT_TOPIC=esp32/sensors
export MQTT_USER=climat
export MQTT_PASSWORD=password

python server.py
```

---

## 🔧 Troubleshooting

| Symptom | Possible Cause | Fix |
|---------|---------------|-----|
| 502 Bad Gateway | Internal nginx cannot reach `climat_web` | Check upstream configuration |
| 500 Internal Server Error | Database hostname not resolved, or column name mismatch (using `sensor_id` instead of `device_id`) | Verify Docker network and update SQL queries |
| No new data, listener logs stopped | MQTT connection dropped, no auto-reconnect | Update `listener.py` with `on_disconnect` handler, rebuild image |
| `/api/data` returns empty while `/api/latest` works | Wrong `device` parameter (e.g., `esp32_main`), or period too short | Use `device=esp32_1` and longer period (e.g., `7d`) |
| Ports busy | Another web server is running | Use host Nginx only, map internal proxy to `127.0.0.1:8080` |
| Tables missing | Init scripts didn't run | Recreate database volume (`docker compose down -v`) |

Useful commands:

```bash
docker compose exec web curl -s http://localhost:8000/api/latest

docker compose exec db psql -U climat -d climat_monitor -c "SELECT count(*) FROM sensor_data;"

docker compose logs mqtt_listener -f
```

---

## 📝 Roadmap

- [ ] MQTT over WebSocket
- [ ] User authentication
- [ ] Multiple device support
- [ ] Telegram/email alerts

---

## 👨‍💻 Author

- GitHub: https://github.com/ciclos5258
- Email: ciclos52582@gmail.com
- Telegram: https://t.me/rendich76

---

## License

MIT
