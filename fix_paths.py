# fix_paths.py — обновляет пути к файлам в PostgreSQL
import os
import sys

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импортируем ВСЁ из app.py, включая модели
from app import app, db, GalleryPhoto, Document, RoomImage

def fix_paths():
    with app.app_context():
        try:
            # Обновить пути в галерее
            result = db.session.execute(
                "UPDATE gallery_photo SET image = REPLACE(image, '/static/uploads/', '/uploads/')"
            )
            print(f"Обновлено gallery_photo: {result.rowcount} записей")
            
            # Обновить пути в документах
            result = db.session.execute(
                "UPDATE document SET file_path = REPLACE(file_path, '/static/uploads/', '/uploads/')"
            )
            print(f"Обновлено document: {result.rowcount} записей")
            
            # Обновить пути в фото номеров
            result = db.session.execute(
                "UPDATE room_image SET image = REPLACE(image, '/static/uploads/', '/uploads/')"
            )
            print(f"Обновлено room_image: {result.rowcount} записей")
            
            db.session.commit()
            print("✅ Все пути обновлены!")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            db.session.rollback()

if __name__ == "__main__":
    fix_paths()