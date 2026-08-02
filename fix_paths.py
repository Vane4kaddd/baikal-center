# fix_paths.py — обновляет пути к файлам в базе данных
import sqlite3
import os

DB_PATH = os.path.join(os.path.expanduser("~"), "data", "instance", "baikal.db")

def fix_paths():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Обновить пути в галерее
        cursor.execute("UPDATE gallery_photo SET image = REPLACE(image, '/static/uploads/', '/uploads/');")
        print(f"Обновлено gallery_photo: {cursor.rowcount} записей")
        
        # Обновить пути в документах
        cursor.execute("UPDATE document SET file_path = REPLACE(file_path, '/static/uploads/', '/uploads/');")
        print(f"Обновлено document: {cursor.rowcount} записей")
        
        # Обновить пути в фото номеров
        cursor.execute("UPDATE room_image SET image = REPLACE(image, '/static/uploads/', '/uploads/');")
        print(f"Обновлено room_image: {cursor.rowcount} записей")
        
        conn.commit()
        conn.close()
        print("✅ Все пути обновлены!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    fix_paths()