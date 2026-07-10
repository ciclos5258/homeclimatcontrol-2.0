```markdown
# 🏗️ Climat Monitor — DevOps Architecture Document

This document describes the deployment architecture, container orchestration, data flow, and operational procedures for the Climat Monitor system. It is intended for developers and DevOps engineers who maintain or extend the project.

---

## 📦 Overview

Climat Monitor is an IoT climate monitoring system composed of the following components:

- **ESP32 + DHT22** – sensor hardware publishing temperature & humidity via MQTT.
- **Mosquitto MQTT broker** – runs on the host machine, receives sensor data.
- **Dockerized services**:
  - `climat_mqtt_listener` – subscribes to MQTT topics and writes records into the database.
  - `climat_db` – TimescaleDB (PostgreSQL 16) for time-series storage.
  - `climat_web` – Flask + Gunicorn REST API, also serves static frontend files.
  - `climat_nginx` – internal reverse proxy that dynamically resolves the web service.
- **Host Nginx** – terminates HTTPS (Let’s Encrypt), proxies requests to the internal Nginx container.

All Docker services are connected via a dedicated bridge network `app-network`.

---

## 🌐 Network & Port Mapping

```
                   ┌───────────────────────────────────────────┐
                   │           app-network (bridge)            │
                   │                                            │
                   │  ┌──────────────────┐                     │
                   │  │ climat_db        │  (5432, internal)   │
                   │  └────────┬─────────┘                     │
                   │           │                                │
                   │  ┌────────▼─────────┐                     │
                   │  │ climat_web       │  (8000, internal)   │
                   │  └────────┬─────────┘                     │
                   │           │                                │
                   │  ┌────────▼─────────┐                     │
                   │  │ climat_nginx     │  (80, internal)     │
                   │  │ ports:           │  mapped 127.0.0.1:8080:80 │
                   │  └──────────────────┘                     │
                   │                                            │
                   │  ┌──────────────────┐                     │
                   │  │climat_mqtt_      │                     │
                   │  │listener          │                     │
                   │  └──────────────────┘                     │
                   └───────────────────────────────────────────┘

Host:
  - Mosquitto (1883)                     <-- ESP32
  - Host Nginx (443→127.0.0.1:8080)      <-- Browser
```

- **climat_db** is not exposed to the host. Connections come only from `climat_web` and `climat_mqtt_listener`.
- **climat_web** does not expose ports to the host; all HTTP traffic goes through Nginx.
- **climat_nginx** listens on host `127.0.0.1:8080`, so it is only reachable from the host’s own processes (i.e., host Nginx).
- **climat_mqtt_listener** needs connectivity to the host’s MQTT broker. The broker’s IP is provided via the `MQTT_BROKER` environment variable (typically `172.17.0.1` or `host.docker.internal`).

---

## 🔄 Data Flow

1. **Ingestion**: ESP32 publishes JSON to `esp32/sensors` on the host Mosquitto broker.
   ```json
   {"device": "esp32_1", "temperature": 24.9, "humidity": 52.5}
   ```
2. **Processing**: `climat_mqtt_listener` receives the message, extracts the `device` field and uses it as `device_id`. It then inserts a row into `sensor_data` table via `psycopg2`.
3. **Storage**: TimescaleDB automatically partitions the hypertable, compresses chunks older than 7 days.
4. **API**: `climat_web` queries `sensor_data` and returns JSON.
5. **Frontend**: Browser loads static files from `climat_web`, then calls `/api/latest`, `/api/stats`, `/api/data` periodically.
6. **Proxying**: Host Nginx (SSL) → `127.0.0.1:8080` → `climat_nginx` (internal) → `climat_web:8000`.

---

## 🐳 Container Details

### 1. climat_db
- Image: `timescale/timescaledb:latest-pg16`
- Healthcheck: `pg_isready -U climat -d climat_monitor`
- Volumes:
  - `pgdata:/var/lib/postgresql/data` – persistent data
  - `./init-db:/docker-entrypoint-initdb.d` – SQL scripts executed on first start
- Environment:
  - `POSTGRES_USER=climat`
  - `POSTGRES_PASSWORD=secret`
  - `POSTGRES_DB=climat_monitor`

### 2. climat_mqtt_listener
- Build: `Dockerfile.listener` (Python 3.11 slim, installs `paho-mqtt`, `psycopg2-binary`)
- Entrypoint: `python listener.py`
- Environment: DB credentials, MQTT broker IP, topic, username/password.
- Important: The script uses the `device` field from incoming JSON as the `device_id` for the database.  
  It includes an `on_disconnect` handler that automatically reconnects to the MQTT broker, preventing data loss after temporary network disruptions.

### 3. climat_web
- Build: `Dockerfile` (Python 3.11 slim, installs `Flask`, `psycopg2`, `flask-cors`, etc.)
- Server: Gunicorn with 4 workers, binding `0.0.0.0:8000`
- Static files: served from `/frontend` by Flask.
- Environment: `DATABASE_URL` for database connection.

### 4. climat_nginx (internal Docker Nginx)
- Image: `nginx:latest`
- Configuration mounted read-only: `./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro`
- Key configuration snippet:
  ```nginx
  resolver 127.0.0.11 valid=30s;
  location / {
      set $backend "climat_web:8000";
      proxy_pass http://$backend;
      ...
  }
  ```
  Using a variable with `resolver` avoids startup failures when `climat_web` is not yet available.

### 5. Host Nginx (system)
- Terminates HTTPS using Let’s Encrypt certificates.
- Proxies all traffic to `http://127.0.0.1:8080` (the internal Nginx).
- Configuration: `/etc/nginx/sites-available/homeclimatcontrol.ru`, enabled via symlink.

---

## 🗄️ Database Schema

The core table is a TimescaleDB hypertable.  
**Note:** the actual column is `device_id`, not `sensor_id`.

```sql
CREATE TABLE IF NOT EXISTS sensor_data (
    time        TIMESTAMPTZ NOT NULL,
    device_id   TEXT NOT NULL,
    temperature DOUBLE PRECISION,
    humidity    DOUBLE PRECISION,
    PRIMARY KEY (time, device_id)
);

SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE, migrate_data => TRUE);
-- Optional compression policy:
-- SELECT add_compression_policy('sensor_data', INTERVAL '7 days');
```

The init script (`init-db/01-init.sql`) is executed automatically when the database volume is created for the first time.  
If the table already exists (e.g., after a volume reuse), no changes are made.

---

## ⚙️ Configuration Management

All non-sensitive settings are defined directly in `docker-compose.yml` under the `environment` key of each service.  
Sensitive values (passwords, API keys) should be moved to an `.env` file and referenced as `${VARIABLE}`.

**Current environment variables (set in compose):**

| Service | Variable | Typical Value |
|---------|----------|---------------|
| db | POSTGRES_USER | climat |
| db | POSTGRES_PASSWORD | secret |
| db | POSTGRES_DB | climat_monitor |
| mqtt_listener | DB_HOST | db |
| mqtt_listener | DB_PORT | 5432 |
| mqtt_listener | DB_NAME | climat_monitor |
| mqtt_listener | DB_USER | climat |
| mqtt_listener | DB_PASSWORD | secret |
| mqtt_listener | MQTT_BROKER | 172.17.0.1 |
| mqtt_listener | MQTT_PORT | 1883 |
| mqtt_listener | MQTT_TOPIC | esp32/sensors |
| mqtt_listener | MQTT_USER | climat |
| mqtt_listener | MQTT_PASSWORD | password |
| web | DATABASE_URL | postgresql://climat:secret@db:5432/climat_monitor |

---

## 🚀 Deployment Procedure

### Initial Deployment

```bash
# Clone repository
git clone https://github.com/ciclos5258/homeclimatcontrol-2.0.git
cd homeclimatcontrol-2.0

# (Optional) create .env with overrides
cp backend/.env.example .env   # if provided

# Build and start all services
docker compose up -d --build
```

Wait for health checks to pass, then set up host Nginx with the SSL configuration (see below).  
After host Nginx is reloaded, the dashboard is available at `https://homeclimatcontrol.ru`.

### Updating Services

After pulling new code from the repository:

```bash
git pull
# Rebuild only the changed images (e.g., web, listener)
docker compose build web mqtt_listener
# Recreate containers with new images
docker compose up -d
```

To force recreation of all containers (e.g., after network/config changes):

```bash
docker compose down
docker compose up -d --build
```

### Rollback

```bash
git checkout <previous-tag>
docker compose down
docker compose up -d --build
```

### Host Nginx Configuration

Create `/etc/nginx/sites-available/homeclimatcontrol.ru`:

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

Enable it:

```bash
sudo ln -s /etc/nginx/sites-available/homeclimatcontrol.ru /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🩺 Monitoring & Health Checks

- **Container status**: `docker compose ps`
- **Logs**: `docker compose logs -f [service]` (e.g., `climat_web`, `climat_mqtt_listener`)
- **Database connectivity**: `docker compose exec db pg_isready -U climat -d climat_monitor`
- **API test**: `docker compose exec web curl -s http://localhost:8000/api/latest`
- **Check network membership**: `docker inspect climat_web | grep -A10 Networks` – both `web` and `db` must be on the same `app-network`.

### Key Metrics to Watch
- `climat_mqtt_listener` logs – should show successful MQTT connections and inserts.
- `climat_web` logs – should show 200 responses; 500 errors usually indicate DB connection issues.
- Host Nginx access/error logs – `/var/log/nginx/access.log`, `error.log`.

---

## 🔧 Troubleshooting Common Issues

| Symptom | Root Cause | Resolution |
|---------|------------|------------|
| `502 Bad Gateway` from host Nginx | Internal `climat_nginx` cannot resolve `climat_web` | Check `nginx/nginx.conf` – ensure it uses `resolver 127.0.0.11` and a variable for `proxy_pass`. |
| `500 Internal Server Error` on `/api/*` | `climat_web` cannot resolve `db` hostname, or SQL queries use incorrect column `sensor_id` instead of `device_id` | Verify `db` service is on `app-network`. Ensure API code references `device_id` in WHERE clauses. |
| MQTT listener warning: `Missing 'device'` | Payload does not contain `device` field | ESP32 should send `"device": "esp32_1"`. If the field is named differently, update `listener.py` accordingly. |
| Port conflict (80/443 already in use) | Another web server on host | Map `climat_nginx` port to `127.0.0.1:8080` only. Let host Nginx manage 80/443. |
| Database tables not created | Init scripts did not run (e.g., reused volume without execution) | Start with fresh volume: `docker compose down -v && docker compose up -d`. |
| No new data in graphs, listener logs stopped after a certain date | MQTT connection dropped and listener lacks reconnection logic | Update `listener.py` with `on_disconnect` handler that loops reconnection. Rebuild the listener image. |
| `/api/data` returns empty array while `/api/latest` shows data | Requested period too short (e.g., `1h`) but last record is older, or wrong `device` parameter | Use longer period (`7d`, `all`) or ensure `device=esp32_1`. Also confirm SQL uses `device_id` column. |

---

## 🔐 Security Considerations

- MQTT requires username/password (configured in Mosquitto’s password file).
- Database credentials are stored in environment variables; for production, move them to a secure vault or Docker secrets.
- All external traffic is encrypted via host Nginx’s HTTPS termination.
- Docker daemon access is restricted; containers run without privileged mode.
- Regular updates of base images (`nginx:latest`, `timescale/timescaledb:latest-pg16`, `python:3.11-slim`) are recommended.

---

## 📚 References

- [Docker Compose specification](https://docs.docker.com/compose/compose-file/)
- [TimescaleDB documentation](https://docs.timescale.com/)
- [Flask](https://flask.palletsprojects.com/)
- [Mosquitto MQTT broker](https://mosquitto.org/)
- [Let’s Encrypt](https://letsencrypt.org/)
```