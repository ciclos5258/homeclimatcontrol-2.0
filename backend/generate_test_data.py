import random
from datetime import datetime, timedelta
import psycopg2
import os

# Конфигурация БД (скопировано из вашего app.py)
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://climat:secret@localhost:5432/climat_monitor'
)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def generate_test_data(num_records=10000, days_back=30):
    """
    Генерирует num_records записей за последние days_back дней.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    
    inserted = 0
    for _ in range(num_records):
        # Случайное время в интервале [start_date, end_date]
        random_seconds = random.randint(0, int((end_date - start_date).total_seconds()))
        timestamp = start_date + timedelta(seconds=random_seconds)
        
        # Реалистичные диапазоны температуры и влажности
        temperature = round(random.uniform(15.0, 35.0), 1)
        humidity = round(random.uniform(20.0, 80.0), 1)
        device_id = "esp32_main"  # или можно случайно выбирать из нескольких
        
        try:
            cur.execute("""
                INSERT INTO sensor_readings (time, device_id, temperature, humidity)
                VALUES (%s, %s, %s, %s)
            """, (timestamp, device_id, temperature, humidity))
            inserted += 1
            if inserted % 1000 == 0:
                print(f"Вставлено {inserted} записей...")
                conn.commit()  # коммитим порциями
        except Exception as e:
            print(f"Ошибка вставки: {e}")
            conn.rollback()
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Готово! Вставлено {inserted} записей.")

if __name__ == "__main__":
    # Можете поменять количество записей и глубину
    generate_test_data(num_records=10000, days_back=30)