```markdown
# 🌡️ Climat Monitor — IoT система мониторинга климата (Docker + TimescaleDB)

Производственная IoT-система для удалённого мониторинга температуры и влажности.  
ESP32 с датчиком DHT22 публикует данные через MQTT; бэкенд на Flask сохраняет их в TimescaleDB (расширение PostgreSQL) и предоставляет REST API. Фронтенд визуализирует историю измерений с помощью Chart.js. Все компоненты контейнеризированы с помощью Docker Compose V2.

**Стек технологий:**
- **Бэкенд:** Python (Flask, paho-mqtt, psycopg2)
- **База данных:** TimescaleDB (PostgreSQL 16)
- **MQTT-брокер:** Mosquitto (на хосте)
- **Прокси:** Nginx (терминация HTTPS, Let's Encrypt)
- **Фронтенд:** нативный JavaScript, HTML5, Chart.js
- **Оркестрация:** Docker Compose V2, BuildKit

---

## 📁 Структура проекта

```
homeclimatcontrol-2.0/
├── backend/
│   ├── server.py               # Flask + MQTT listener
│   ├── requirements.txt
│   └── .env                    # переменные окружения (не в Git)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── chart.js
├── nginx/
│   └── nginx.conf              # конфиг Nginx для HTTPS
├── docker-compose.yml
├── Dockerfile
└── .dockerignore
```

## 🚀 Возможности

- 📡 **Приём MQTT** – подписка на топик `esp32/sensors`, сохранение каждого измерения
- 💾 **TimescaleDB** – автоматическое сжатие чанков старше 7 дней, гипертаблицы для быстрых временны́х запросов
- 📊 **REST API** – сырые данные, последнее значение, статистика (среднее/мин/макс) и данные с группировкой по времени (час/день)
- 📈 **Веб-дашборд** – интерактивный график Chart.js с выбором периода (1ч, 6ч, 24ч, 7д, 30д, всё)
- 🐳 **Полная контейнеризация** – бэкенд и БД в Docker; тома для постоянного хранения
- 🔒 **Nginx reverse proxy** – HTTPS + Let’s Encrypt (опционально)
- ⚙️ **Настройка через окружение** – секреты в `.env`, не зашиты в коде

---

## 🔧 Архитектура (текущая версия)

```
ESP32 + DHT22
     │
     ▼ (MQTT, топик esp32/sensors)
┌─────────────┐     ┌─────────────────────────────────┐
│  Mosquitto  │────▶│       Flask App (контейнер)     │
│ (на хосте)  │     │   - подписка на MQTT            │
└─────────────┘     │   - запись в БД через psycopg2  │
                    └──────────────┬──────────────────┘
                                   │ (REST API)
                                   ▼
                          ┌─────────────────┐
                          │ TimescaleDB     │
                          │ (контейнер db)  │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ Nginx (опционально)│
                          │ HTTPS:443 → web │
                          └─────────────────┘
                                   │
                                   ▼
                          Веб-интерфейс (браузер)
```

**Сеть:** Все контейнеры используют выделенную bridge-сеть; БД не публикует порты на хост.  
**MQTT:** Для доступа к брокеру на хосте Ubuntu используется `host.docker.internal` и `extra_hosts`.

---

## 📡 API эндпоинты

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `GET` | `/api/data?period=1h&device=esp32_main` | Данные с группировкой по времени (сырые для коротких периодов, средние за день – для длинных) |
| `GET` | `/api/latest` | Последнее измерение (температура, влажность, время) |
| `GET` | `/api/stats` | Общая статистика: количество записей, среднее/мин/макс по обоим датчикам |
| `GET` | `/api/health` | Проверка здоровья (подключение к БД) |

**Параметры запроса для `/api/data`:**
- `period` – `1h`, `6h`, `24h`, `7d`, `30d`, `all`
- `device` – идентификатор устройства (по умолчанию `esp32_main`)

## 📊 Веб-интерфейс

- **Текущие значения** – последние показания температуры и влажности
- **Интерактивный график** – выбор периода, масштабирование, наведение для точных значений
- **Адаптивный дизайн** – работает на десктопах и мобильных устройствах
- **Автообновление** – опционально, каждые 30 секунд

---

## 🐳 Запуск через Docker Compose (production)

### Требования
- Ubuntu 24.04+ (или любой Linux с Docker Engine 24+)
- Плагин Docker Compose (команда `docker compose`, не устаревшая `docker-compose`)
- MQTT-брокер Mosquitto, установленный **на хосте** (не в контейнере)
- Git, curl, доменное имя с DNS-записью на ваш сервер (для HTTPS)

### 1. Клонировать репозиторий и подготовить окружение

```bash
git clone https://github.com/ciclos5258/homeclimatcontrol-2.0.git
cd homeclimatcontrol-2.0
cp backend/.env.example backend/.env   # создать из шаблона
```

### 2. Настроить `.env` (пример)

```env
# База данных (используется внутри Docker-сети)
DATABASE_URL=postgresql://climat:secret@db:5432/climat_monitor

# MQTT-брокер (на хосте)
MQTT_BROKER=host.docker.internal
MQTT_PORT=1883
MQTT_TOPIC=esp32/sensors
MQTT_USER=python
MQTT_PASSWORD=ваш_пароль_mqtt

# Необязательно: порт для веб-сервера
WEB_PORT=5002
```

### 3. Настроить MQTT-брокер на хосте для приёма подключений из Docker

Отредактируйте `/etc/mosquitto/mosquitto.conf`:

```conf
listener 1883 0.0.0.0
allow_anonymous false
password_file /etc/mosquitto/passwd
```

Создайте пользователя `python`:

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd python
sudo systemctl restart mosquitto
```

### 4. Собрать и запустить через Docker Compose

```bash
docker compose up -d --build
```

Посмотреть логи:

```bash
docker compose logs -f web
```

### 5. Настройка Nginx reverse proxy (опционально, но рекомендуется)

Пример `nginx.conf` (разместите в `./nginx/`):

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

Запустите контейнер Nginx (если он включён в `docker-compose.yml`).

### 6. Настроить файрвол (UFW)

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 1883/tcp   # если ESP32 подключается напрямую снаружи
sudo ufw enable
```

---

## 🔐 Безопасность

- **MQTT аутентификация** – имя пользователя/пароль (не анонимный доступ)
- **База данных** – не публикуется на хост, доступна только внутри Docker-сети
- **Секреты** – хранятся в `.env`, не попадают в Git
- **CORS** – ограничен для вашего домена (по умолчанию в коде `CORS(app)` открытый – настройте для продакшена)
- **Nginx** – терминация HTTPS, скрывает порт Flask от интернета

---

## 🧪 Разработка (без Docker)

Установите зависимости Python, создайте виртуальное окружение и запустите:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Бэкенд попытается подключиться к локальному PostgreSQL (укажите `DATABASE_URL` соответственно) и MQTT-брокеру на `localhost:1883`.

---

## 📝 Планы / дорожная карта

- [ ] Добавить MQTT over WebSocket для обновлений в реальном времени
- [ ] Реализовать аутентификацию пользователей (Flask‑Login)
- [ ] Поддержка нескольких устройств (уже заложено в схеме БД)
- [ ] Оповещения (telegram/email при превышении порогов)

---

## 👨‍💻 Автор

- GitHub: [github.com/ciclos5258](https://github.com/ciclos5258)
- Email: [ciclos52582@gmail.com](mailto:ciclos52582@gmail.com)
- Telegram: [@rendich76](https://t.me/rendich76)

---

## 📜 Лицензия

MIT
```
