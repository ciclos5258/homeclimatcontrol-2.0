```markdown
# 🏗️ Climat Monitor — Архитектура развёртывания (DevOps)

Документ описывает архитектуру развёртывания, оркестрацию контейнеров, поток данных и эксплуатационные процедуры системы Climat Monitor. Предназначен для разработчиков и DevOps-инженеров, сопровождающих или дорабатывающих проект.

---

## 📦 Обзор

Climat Monitor — IoT-система климатического мониторинга, состоящая из следующих компонентов:

- **ESP32 + DHT22** – аппаратный датчик, публикующий температуру и влажность по MQTT.
- **Mosquitto MQTT‑брокер** – работает на хостовой машине, принимает данные от датчиков.
- **Контейнеризированные сервисы**:
  - `climat_mqtt_listener` – подписывается на MQTT‑топики и записывает записи в базу данных.
  - `climat_db` – TimescaleDB (PostgreSQL 16) для хранения временных рядов.
  - `climat_web` – Flask + Gunicorn, REST API и раздача статических файлов фронтенда.
  - `climat_nginx` – внутренний обратный прокси с динамическим разрешением имени веб‑сервиса.
- **Хостовый Nginx** – терминирует HTTPS (Let’s Encrypt), проксирует запросы во внутренний контейнер Nginx.

Все Docker-сервисы связаны через выделенную bridge-сеть `app-network`.

---

## 🌐 Сетевая схема и проброс портов

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

Хост:
  - Mosquitto (1883)                     <-- ESP32
  - Хостовый Nginx (443→127.0.0.1:8080)  <-- Браузер
```

- **climat_db** не публикуется наружу. Подключения идут только от `climat_web` и `climat_mqtt_listener`.
- **climat_web** не пробрасывает порты на хост; весь HTTP‑трафик проходит через Nginx.
- **climat_nginx** слушает `127.0.0.1:8080` на хосте, поэтому доступен только с локальных процессов (т.е. хостовому Nginx).
- **climat_mqtt_listener** должен иметь связь с MQTT‑брокером на хосте. IP‑адрес брокера задаётся переменной окружения `MQTT_BROKER` (обычно `172.17.0.1` или `host.docker.internal`).

---

## 🔄 Поток данных

1. **Получение данных**: ESP32 публикует JSON в топик `esp32/sensors` брокера Mosquitto на хосте.
   ```json
   {"device": "esp32_1", "temperature": 24.9, "humidity": 52.5}
   ```
2. **Обработка**: `climat_mqtt_listener` принимает сообщение, проверяет/извлекает поля (использует `device` как `sensor_id`) и вставляет строку в таблицу `sensor_data` через `psycopg2`.
3. **Хранение**: TimescaleDB автоматически партиционирует гипертаблицу, сжимает чанки старше 7 дней.
4. **API**: `climat_web` запрашивает `sensor_data` и возвращает JSON.
5. **Фронтенд**: Браузер загружает статику с `climat_web`, затем периодически вызывает `/api/latest`, `/api/stats`, `/api/data`.
6. **Проксирование**: Хостовый Nginx (SSL) → `127.0.0.1:8080` → `climat_nginx` (внутренний) → `climat_web:8000`.

---

## 🐳 Детали контейнеров

### 1. climat_db
- Образ: `timescale/timescaledb:latest-pg16`
- Проверка здоровья: `pg_isready -U climat -d climat_monitor`
- Тома:
  - `pgdata:/var/lib/postgresql/data` – постоянное хранилище
  - `./init-db:/docker-entrypoint-initdb.d` – SQL‑скрипты, выполняемые при первом старте
- Переменные окружения:
  - `POSTGRES_USER=climat`
  - `POSTGRES_PASSWORD=secret`
  - `POSTGRES_DB=climat_monitor`

### 2. climat_mqtt_listener
- Сборка: `Dockerfile.listener` (Python 3.11 slim, устанавливает `paho-mqtt`, `psycopg2-binary`)
- Точка входа: `python listener.py`
- Переменные окружения: учётные данные БД, IP MQTT‑брокера, топик, логин/пароль.
- Важно: скрипт адаптируется к названиям полей – если отсутствует `sensor_id`, используется `device`.

### 3. climat_web
- Сборка: `Dockerfile` (Python 3.11 slim, устанавливает `Flask`, `psycopg2`, `flask-cors` и др.)
- Сервер: Gunicorn с 4 воркерами, слушает `0.0.0.0:8000`
- Статика: отдаётся Flask из каталога `/frontend`.
- Переменные окружения: `DATABASE_URL` для подключения к БД.

### 4. climat_nginx (внутренний Docker Nginx)
- Образ: `nginx:latest`
- Конфигурация монтируется только для чтения: `./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro`
- Ключевой фрагмент конфигурации:
  ```nginx
  resolver 127.0.0.11 valid=30s;
  location / {
      set $backend "climat_web:8000";
      proxy_pass http://$backend;
      ...
  }
  ```
  Использование переменной с `resolver` позволяет избежать ошибок при старте, когда `climat_web` ещё не готов.

### 5. Хостовый Nginx (системный)
- Терминирует HTTPS с использованием сертификатов Let’s Encrypt.
- Проксирует весь трафик на `http://127.0.0.1:8080` (внутренний Nginx).
- Конфигурация: `/etc/nginx/sites-available/homeclimatcontrol.ru`, активирована симлинком.

---

## 🗄️ Схема базы данных

Основная таблица – это гипертаблица TimescaleDB:

```sql
CREATE TABLE sensor_data (
    id SERIAL,
    sensor_id TEXT NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('sensor_data', 'timestamp');
-- Опциональная политика сжатия:
-- SELECT add_compression_policy('sensor_data', INTERVAL '7 days');
```

Инициализирующий скрипт (`init-db/01-init.sql`) выполняется автоматически при первом создании тома базы данных.  
Если таблица уже существует (например, при повторном использовании тома), изменения не применяются.

---

## ⚙️ Управление конфигурацией

Все параметры, не содержащие секретов, заданы непосредственно в `docker-compose.yml` в секции `environment` каждого сервиса.  
Чувствительные значения (пароли, ключи API) рекомендуется выносить в `.env`-файл и ссылаться на них как `${VARIABLE}`.

**Текущие переменные окружения (заданы в compose):**

| Сервис | Переменная | Типичное значение |
|--------|------------|-------------------|
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

## 🚀 Процедура развёртывания

### Первичное развёртывание

```bash
# Клонирование репозитория
git clone https://github.com/ciclos5258/homeclimatcontrol-2.0.git
cd homeclimatcontrol-2.0

# (Опционально) создать .env с переопределениями
cp backend/.env.example .env   # если есть

# Сборка и запуск всех сервисов
docker compose up -d --build
```

Дождитесь прохождения проверок здоровья, затем настройте хостовый Nginx с SSL (см. ниже).  
После перезагрузки хостового Nginx панель управления будет доступна по адресу `https://homeclimatcontrol.ru`.

### Обновление сервисов

После получения нового кода из репозитория:

```bash
git pull
# Пересобрать только изменившиеся образы (например, web, listener)
docker compose build web mqtt_listener
# Пересоздать контейнеры с новыми образами
docker compose up -d
```

Для принудительного пересоздания всех контейнеров (например, после изменений сети/конфигурации):

```bash
docker compose down
docker compose up -d --build
```

### Откат

```bash
git checkout <предыдущий-тег>
docker compose down
docker compose up -d --build
```

### Настройка хостового Nginx

Создайте `/etc/nginx/sites-available/homeclimatcontrol.ru`:

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

Активируйте конфигурацию:

```bash
sudo ln -s /etc/nginx/sites-available/homeclimatcontrol.ru /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🩺 Мониторинг и проверки здоровья

- **Статус контейнеров**: `docker compose ps`
- **Логи**: `docker compose logs -f [сервис]` (например, `climat_web`, `climat_mqtt_listener`)
- **Доступность базы данных**: `docker compose exec db pg_isready -U climat -d climat_monitor`
- **Тест API**: `docker compose exec web curl -s http://localhost:8000/api/latest`
- **Проверка сетевой принадлежности**: `docker inspect climat_web | grep -A10 Networks` – оба контейнера `web` и `db` должны находиться в одной сети `app-network`.

### Ключевые метрики для отслеживания
- Логи `climat_mqtt_listener` – должны показывать успешные подключения к MQTT и вставки записей.
- Логи `climat_web` – должны содержать ответы 200; ошибки 500 обычно указывают на проблемы подключения к БД.
- Логи доступа и ошибок хостового Nginx – `/var/log/nginx/access.log`, `error.log`.

---

## 🔧 Устранение типовых неполадок

| Симптом | Корневая причина | Решение |
|---------|------------------|---------|
| `502 Bad Gateway` от хостового Nginx | Внутренний `climat_nginx` не может разрешить `climat_web` | Проверьте `nginx/nginx.conf` – должен использовать `resolver 127.0.0.11` и переменную для `proxy_pass`. |
| `500 Internal Server Error` на `/api/*` | `climat_web` не может разрешить имя `db` | Убедитесь, что у сервиса `db` есть `networks: - app-network` в compose. Примените через `docker compose down && docker compose up -d`. |
| Предупреждение MQTT‑слушателя: `Missing 'sensor_id'` | ESP32 отправляет `device` вместо `sensor_id` | Отредактируйте `listener.py`: `sensor_id = data.get('sensor_id', data.get('device'))`. Пересоберите образ слушателя. |
| Конфликт портов (80/443 уже заняты) | Другой веб‑сервер на хосте | Пробросьте порт `climat_nginx` только на `127.0.0.1:8080`. Хостовый Nginx должен быть единственным слушателем на 80/443. |
| Таблицы базы данных не созданы | Скрипты инициализации не выполнились (например, при повторном использовании тома) | Запустите с чистым томом: `docker compose down -v && docker compose up -d`. |

---

## 🔐 Вопросы безопасности

- MQTT требует имя пользователя и пароль (настроено в файле паролей Mosquitto).
- Учётные данные базы данных хранятся в переменных окружения; для промышленной эксплуатации их следует вынести в защищённое хранилище или Docker secrets.
- Весь внешний трафик шифруется через терминацию HTTPS хостовым Nginx.
- Доступ к демону Docker ограничен; контейнеры запускаются без привилегированного режима.
- Рекомендуется регулярное обновление базовых образов (`nginx:latest`, `timescale/timescaledb:latest-pg16`, `python:3.11-slim`).

---

## 📚 Ссылки

- [Спецификация Docker Compose](https://docs.docker.com/compose/compose-file/)
- [Документация TimescaleDB](https://docs.timescale.com/)
- [Flask](https://flask.palletsprojects.com/)
- [Mosquitto MQTT брокер](https://mosquitto.org/)
- [Let’s Encrypt](https://letsencrypt.org/)

---

```