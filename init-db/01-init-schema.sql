-- Создаем расширение TimescaleDB (если оно еще не создано)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Создаем таблицу для хранения данных с ESP32
CREATE TABLE IF NOT EXISTS sensor_data (
    time        TIMESTAMPTZ NOT NULL, -- Временная метка
    sensor_id   TEXT        NOT NULL, -- ID датчика (например, esp32_1)
    temperature DOUBLE PRECISION,     -- Температура
    humidity    DOUBLE PRECISION      -- Влажность
);

-- Превращаем таблицу в hypertable, автоматически партиционируя по времени
SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);