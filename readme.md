Ниже представлена документация для вашей текущей версии проекта — с учётом использования **PostgreSQL + TimescaleDB**, **Docker Compose V2**, **MQTT на хосте** и **Nginx**. Формат и стиль взяты из вашего примера, но адаптированы под реальную архитектуру.

---

[ru Читать на русском](readme_ru.md)

```markdown
# 🌡️ Climat Monitor — IoT Climate Monitoring System (Docker + TimescaleDB)

A production-grade IoT system for remote temperature and humidity monitoring.  
The ESP32 microcontroller (DHT22) publishes data via MQTT; the Flask backend stores it in TimescaleDB (PostgreSQL extension) and exposes a REST API. The web frontend visualises historical data using Chart.js. All components are containerised with Docker Compose V2.

**Stack:**
- **Backend:** Python (Flask, paho-mqtt, psycopg2)
- **Database:** TimescaleDB (PostgreSQL 16)
- **MQTT Broker:** Mosquitto (running on host machine)
- **Proxy:** Nginx (HTTPS termination, Let's Encrypt)
- **Frontend:** JavaScript (native), HTML5, Chart.js
- **Orchestration:** Docker Compose V2, BuildKit

---

## 📁 Project Structure

```
homeclimatcontrol-2.0/
├── backend/
│   ├── server.py               # Flask + MQTT listener
│   ├── requirements.txt
│   └── .env                    # environment variables (not committed)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── chart.js
├── nginx/
│   └── nginx.conf              # HTTPS proxy config
├── docker-compose.yml
├── Dockerfile
└── .dockerignore
```

## 🚀 Features

- 📡 **MQTT ingestion** – listens to `esp32/sensors` topic, stores every reading
- 💾 **TimescaleDB** – automatic compression of chunks older than 7 days, hypertables for fast time‑series queries
- 📊 **REST API** – raw data, latest value, aggregated statistics (avg/min/max) and time‑bucketed data (hour/day)
- 📈 **Web dashboard** – interactive Chart.js graph with selectable time periods (1h, 6h, 24h, 7d, 30d, all)
- 🐳 **Full containerisation** – backend and database run in Docker; volumes for persistent storage
- 🔒 **Nginx reverse proxy** – HTTPS + Let’s Encrypt (optional but recommended)
- ⚙️ **Environment‑based configuration** – no hard‑coded secrets, uses `.env` and `docker-compose.yml`

---

## 🔧 Architecture (current version)

```
ESP32 + DHT22
     │
     ▼ (MQTT, topic esp32/sensors)
┌─────────────┐     ┌─────────────────────────────────┐
│  Mosquitto  │────▶│       Flask App (container)      │
│ (on host)   │     │   - subscribes to MQTT           │
└─────────────┘     │   - stores via psycopg2          │
                    └──────────────┬──────────────────┘
                                   │ (REST API)
                                   ▼
                          ┌─────────────────┐
                          │ TimescaleDB     │
                          │ (db container)  │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ Nginx (optional)│
                          │ HTTPS:443 → web │
                          └─────────────────┘
                                   │
                                   ▼
                          Web Interface (browser)
```

**Network:** All containers share a dedicated bridge network; the database is not exposed to the host (no `ports` for `db`).  
**MQTT access:** Uses `host.docker.internal` + `extra_hosts` to reach the broker on the Ubuntu host.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/data?period=1h&device=esp32_main` | Time‑bucketed data (raw for short periods, daily averages for long periods) |
| `GET` | `/api/latest` | Most recent reading (temperature, humidity, timestamp) |
| `GET` | `/api/stats` | Overall statistics: total readings, average/min/max for both sensors |
| `GET` | `/api/health` | Health check (database connectivity) |

**Query parameters for `/api/data`:**
- `period` – `1h`, `6h`, `24h`, `7d`, `30d`, `all`
- `device` – device ID (default: `esp32_main`)

## 📊 Web Interface

- **Current values** – latest temperature and humidity
- **Interactive chart** – select period, zoom/pan, hover for exact values
- **Responsive design** – works on desktop and mobile
- **Auto‑refresh** – optionally fetches new data every 30 seconds

---

## 🐳 Running with Docker Compose (production)

### Prerequisites
- Ubuntu 24.04+ (or any Linux with Docker Engine 24+)
- Docker Compose Plugin (`docker compose` command, not legacy `docker-compose`)
- Mosquitto MQTT broker **installed on the host** (not in a container)
- Git, curl, and a domain name with DNS pointing to your server (for HTTPS)

### 1. Clone the repository and prepare the environment

```bash
git clone https://github.com/ciclos5258/homeclimatcontrol-2.0.git
cd homeclimatcontrol-2.0
cp backend/.env.example backend/.env   # create from template
```

### 2. Configure `.env` (example)

```env
# Database (used inside Docker network)
DATABASE_URL=postgresql://climat:secret@db:5432/climat_monitor

# MQTT broker (on host)
MQTT_BROKER=host.docker.internal
MQTT_PORT=1883
MQTT_TOPIC=esp32/sensors
MQTT_USER=python
MQTT_PASSWORD=your_mqtt_password

# Optional: web port mapping
WEB_PORT=5002
```

### 3. Ensure MQTT broker on host accepts connections from Docker

Edit `/etc/mosquitto/mosquitto.conf`:

```conf
listener 1883 0.0.0.0
allow_anonymous false
password_file /etc/mosquitto/passwd
```

Create user `python`:

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd python
sudo systemctl restart mosquitto
```

### 4. Build and run with Docker Compose

```bash
docker compose up -d --build
```

Check logs:

```bash
docker compose logs -f web
```

### 5. Set up Nginx reverse proxy (optional but recommended)

Example `nginx.conf` (placed in `./nginx/`):

```nginx
server {
    listen 80;
    server_name homeclimatcontrol.ru;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name homeclimatcontrol.ru;

    ssl_certificate     /etc/letsencrypt/live/homeclimatcontrol.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/homeclimatcontrol.ru/privkey.pem;

    location / {
        proxy_pass http://web:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Run Nginx container (already included in `docker-compose.yml` if you uncomment it).

### 6. Update firewall (UFW)

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 1883/tcp   # if external ESP32 connects directly
sudo ufw enable
```

---

## 🔐 Security

- **MQTT authentication** – username/password (not anonymous)
- **Database** – not exposed to host, only reachable via internal Docker network
- **Secrets** – stored in `.env`, never committed to Git
- **CORS** – restricted to your domain (configured in Flask, though `CORS(app)` is open by default – adjust for production)
- **Nginx** – handles HTTPS termination, hides Flask port from the internet

---

## 🧪 Development (without Docker)

Install Python dependencies, create a virtual environment, and run:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

The backend will try to connect to a local PostgreSQL instance (set `DATABASE_URL` accordingly) and an MQTT broker at `localhost:1883`.

---

## 📝 To-Do / Roadmap

- [ ] Add MQTT over WebSocket for real‑time frontend updates
- [ ] Implement user authentication (Flask‑Login)
- [ ] Store multiple devices (already supported in DB schema)
- [ ] Add alerting (telegram/email when thresholds are exceeded)

---

## 👨‍💻 Author

- GitHub: [github.com/ciclos5258](https://github.com/ciclos5258)
- Email: [ciclos52582@gmail.com](mailto:ciclos52582@gmail.com)
- Telegram: [@rendich76](https://t.me/rendich76)

---

## Licence

MIT
