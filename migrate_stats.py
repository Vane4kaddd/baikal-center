# migrate_stats.py — добавляет таблицы статистики без потери данных
import os
import sys
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Date, DateTime, UniqueConstraint
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
    
    # Таблица site_stats (обновлённая)
    site_stats = Table(
        'site_stats', metadata,
        Column('id', Integer, primary_key=True),
        Column('total_visits', Integer, server_default='0'),
        Column('today_visits', Integer, server_default='0'),
        Column('yesterday_visits', Integer, server_default='0'),
        Column('total_unique', Integer, server_default='0'),
        Column('today_unique', Integer, server_default='0'),
        Column('yesterday_unique', Integer, server_default='0'),
        Column('last_updated', Date, nullable=True)
    )
    
    # Таблица visitor_stat
    visitor_stat = Table(
        'visitor_stat', metadata,
        Column('id', Integer, primary_key=True),
        Column('ip', String(45), nullable=False),
        Column('visit_date', Date, nullable=False),
        Column('first_visit', DateTime, nullable=True),
        Column('last_visit', DateTime, nullable=True),
        UniqueConstraint('ip', 'visit_date', name='unique_ip_day')
    )
    
    # Создаём таблицы
    metadata.create_all(engine)
    print("✅ Таблицы site_stats и visitor_stat созданы (или уже существуют)")

if __name__ == "__main__":
    migrate()
