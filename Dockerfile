# Берём лёгкий официальный образ Python
FROM python:3.11-slim

# Ставим рабочую папку внутри контейнера
WORKDIR /

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Копируем список зависимостей и устанавливаем их
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Говорим Flask работать на порту 5002
EXPOSE 5002

# Команда запуска при старте контейнера
RUN pip install gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "backend.server:app"]
