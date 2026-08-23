# migrate_stats.py — добавляет таблицу site_stats без потери данных
import os
import sys
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, Date
from sqlalchemy.orm import sessionmaker

# Настройка для Amvera
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'baikal')

DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

def migrate():
    engine = create_engine(DATABASE_URL)
    metadata = MetaData()
    
    # Определяем структуру таблицы
    site_stats = Table(
        'site_stats', metadata,
        Column('id', Integer, primary_key=True),
        Column('total_visits', Integer, server_default='0'),
        Column('today_visits', Integer, server_default='0'),
        Column('yesterday_visits', Integer, server_default='0'),
        Column('last_updated', Date, nullable=True)
    )
    
    # Создаём таблицу, если её нет
    metadata.create_all(engine)
    print("✅ Таблица site_stats создана (или уже существует)")

if __name__ == "__main__":
    migrate()