# 🌡️ Climat Monitor — IoT-система мониторинга температуры и влажности (Docker + TimescaleDB)

Производственная IoT-система для удалённого мониторинга температуры и влажности.
Микроконтроллер ESP32 с датчиком DHT22 публикует данные через MQTT, отдельный MQTT Listener принимает сообщения и сохраняет их в TimescaleDB (расширение PostgreSQL). Flask-приложение предоставляет REST API и обслуживает веб-интерфейс с визуализацией исторических данных с помощью Chart.js. Все компоненты развертываются в Docker с использованием Docker Compose V2.

**Используемый стек:**

* **Backend:** Python (Flask, Gunicorn)
* **MQTT Listener:** Python (paho-mqtt, psycopg2) — отдельный контейнер
* **База данных:** TimescaleDB (PostgreSQL 16)
* **MQTT-брокер:** Mosquitto (запущен на хост-машине)
* **Прокси:** Nginx (внутри Docker + системный Nginx для HTTPS и Let's Encrypt)
* **Frontend:** JavaScript (Vanilla JS), HTML5, Chart.js
* **Оркестрация:** Docker Compose V2, BuildKit

---

# 📁 Структура проекта

```text
homeclimatcontrol-2.0/
├── backend/
│   ├── server.py               # Flask REST API
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── app.js                  # Основная логика приложения
│   └── chart.js                # Построение графиков
├── nginx/
│   └── nginx.conf              # Конфигурация внутреннего Nginx
├── init-db/
│   └── 01-init.sql             # Инициализация базы данных
├── docker-compose.yml
├── Dockerfile                  # Контейнер climat_web
├── Dockerfile.listener         # Контейнер climat_mqtt_listener
├── listener.py                 # MQTT Listener
└── .dockerignore
```

---

# 🚀 Возможности

* 📡 Приём данных по MQTT в отдельном контейнере
* 💾 Хранение данных в TimescaleDB с использованием hypertable и автоматическим сжатием старых чанков
* 📊 REST API для получения последних показаний, статистики и исторических данных
* 📈 Интерактивный веб-интерфейс на Chart.js с выбором периода отображения
* 🐳 Полная контейнеризация проекта с помощью Docker Compose
* 🔒 Работа через HTTPS благодаря связке Nginx + Let's Encrypt
* ⚙️ Гибкая настройка параметров через переменные окружения

---

# 🔧 Архитектура

```text
ESP32 + DHT22
     │
     ▼ (MQTT, esp32/sensors)
┌─────────────┐
│ Mosquitto   │ (хост)
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│ climat_mqtt_listener │
│ принимает сообщения  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────┐
│ climat_db        │
│ TimescaleDB      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ climat_web       │
│ Flask + Gunicorn │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ climat_nginx     │
│ Внутренний Nginx │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Системный Nginx  │
│ HTTPS            │
└────────┬─────────┘
         │
         ▼
      Браузер
```

**Особенности архитектуры**

* Все контейнеры работают в отдельной сети `app-network`.
* База данных недоступна извне и используется только внутренними сервисами.
* MQTT Listener подключается к Mosquitto, установленному на хост-машине.
* Внутренний Nginx использует динамический upstream (`resolver 127.0.0.11`), благодаря чему корректно переживает перезапуск контейнеров.

---

# 📡 REST API

| Метод | Endpoint                                | Назначение                   |
| ----- | --------------------------------------- | ---------------------------- |
| `GET` | `/api/latest`                           | Последние показания датчиков |
| `GET` | `/api/stats`                            | Общая статистика             |
| `GET` | `/api/data?period=1h&device=esp32_main` | Исторические данные          |
| `GET` | `/api/health`                           | Проверка состояния сервиса   |

### Параметры `/api/data`

* `period` — `1h`, `6h`, `24h`, `7d`, `30d`, `all`
* `device` — идентификатор устройства (`esp32_main` по умолчанию)

---

# 📊 Веб-интерфейс

* **Главная** — текущая температура и влажность
* **История** — графики изменения показаний
* **Статистика** — средние, минимальные и максимальные значения
* **Настройки** — пороги срабатывания и уведомления
* **Адаптивный дизайн** — поддержка мобильных устройств
* **Автообновление** — новые данные каждые 3 секунды

---

# 🐳 Запуск проекта

## Требования

* Ubuntu 24.04+ или любой Linux с Docker Engine 24+
* Docker Compose V2
* MQTT-брокер Mosquitto на хост-машине
* Git
* Домен (при использовании HTTPS)

## 1. Клонирование репозитория

```bash
git clone https://github.com/ciclos5258/homeclimatcontrol-2.0.git
cd homeclimatcontrol-2.0
```

## 2. Настройка переменных окружения

```env
DATABASE_URL=postgresql://climat:secret@db:5432/climat_monitor
MQTT_BROKER=172.17.0.1
MQTT_PORT=1883
MQTT_TOPIC=esp32/sensors
MQTT_USER=climat
MQTT_PASSWORD=password
```

## 3. Настройка Mosquitto

```conf
listener 1883 0.0.0.0
allow_anonymous false
password_file /etc/mosquitto/passwd
```

Создание пользователя:

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd climat
sudo systemctl restart mosquitto
```

## 4. Сборка и запуск

```bash
docker compose up -d --build
```

Просмотр логов:

```bash
docker compose logs -f
```

## 5. Настройка Nginx

Используйте системный Nginx для обработки HTTPS и проксирования запросов на внутренний контейнер `climat_nginx`.

После изменения конфигурации:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 6. Настройка UFW

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 1883/tcp
sudo ufw enable
```

---

# 🔐 Безопасность

* Авторизация MQTT по логину и паролю
* База данных изолирована внутри Docker-сети
* Конфиденциальные данные рекомендуется хранить в `.env`
* Ограничение CORS
* HTTPS обеспечивается с помощью Let's Encrypt

---

# 🧪 Локальная разработка

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

# 🔧 Решение распространённых проблем

| Проблема                  | Возможная причина                   | Решение                      |
| ------------------------- | ----------------------------------- | ---------------------------- |
| 502 Bad Gateway           | Flask недоступен                    | Проверить конфигурацию Nginx |
| 500 Internal Server Error | Нет подключения к БД                | Проверить Docker-сеть        |
| Нет данных                | MQTT Listener не получает сообщения | Проверить логи Listener      |
| Заняты порты 80/443       | Другой веб-сервер использует порты  | Использовать системный Nginx |
| Таблицы отсутствуют       | SQL-инициализация не выполнилась    | Пересоздать том БД           |

Полезные команды:

```bash
docker compose exec web curl http://localhost:8000/api/latest

docker compose exec db psql -U climat -d climat_monitor

docker logs climat_mqtt_listener -f
```

---

# 📝 Планы развития

* [ ] Поддержка MQTT over WebSocket
* [ ] Аутентификация пользователей
* [ ] Поддержка нескольких устройств
* [ ] Уведомления через Telegram и Email
* [ ] Экспорт данных в CSV и Excel

---

# 👨‍💻 Автор

**GitHub:** https://github.com/ciclos5258

**Email:** [ciclos52582@gmail.com](mailto:ciclos52582@gmail.com)

**Telegram:** https://t.me/rendich76

---

# 📄 Лицензия

MIT
