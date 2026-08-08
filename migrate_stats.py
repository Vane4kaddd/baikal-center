# migrate_stats.py
import os
import sys
from sqlalchemy import create_engine, text

DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'baikal')

DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

def migrate():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Добавляем колонки
        for col in ['total_unique', 'today_unique', 'yesterday_unique']:
            try:
                conn.execute(text(f"ALTER TABLE site_stats ADD COLUMN {col} INTEGER DEFAULT 0"))
                print(f"✅ Колонка {col} добавлена")
            except Exception as e:
                if 'already exists' in str(e):
                    print(f"⚠️ Колонка {col} уже существует")
                else:
                    print(f"❌ Ошибка: {e}")
        
        # Создаём таблицу visitor_stat
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS visitor_stat (
                    id SERIAL PRIMARY KEY,
                    ip VARCHAR(45) NOT NULL,
                    visit_date DATE NOT NULL,
                    first_visit TIMESTAMP DEFAULT NOW(),
                    last_visit TIMESTAMP DEFAULT NOW(),
                    UNIQUE(ip, visit_date)
                )
            """))
            print("✅ Таблица visitor_stat создана")
        except Exception as e:
            print(f"❌ Ошибка создания visitor_stat: {e}")
        
        conn.commit()

if __name__ == "__main__":
    migrate()
