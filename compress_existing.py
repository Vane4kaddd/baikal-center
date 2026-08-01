# compress_existing.py
import os
from PIL import Image
from werkzeug.utils import secure_filename

def compress_image(filepath, output_path=None, max_size=(1200, 800), quality=85):
    """Сжимает одно изображение"""
    try:
        img = Image.open(filepath)
        
        # Конвертируем в RGB
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Уменьшаем размер
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Сохраняем
        if output_path is None:
            output_path = filepath
        
        img.save(output_path, format='JPEG', quality=quality, optimize=True, progressive=True)
        print(f"✅ Сжато: {filepath}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {filepath} - {e}")
        return False


def compress_folder(folder_path, max_size=(1200, 800), quality=85):
    """Сжимает все изображения в папке"""
    if not os.path.exists(folder_path):
        print(f"❌ Папка не найдена: {folder_path}")
        return
    
    compressed = 0
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                filepath = os.path.join(root, file)
                if compress_image(filepath, max_size=max_size, quality=quality):
                    compressed += 1
    
    print(f"\n✅ Сжато {compressed} файлов в папке {folder_path}")


if __name__ == '__main__':
    # Сжать все фото в галерее
    compress_folder('static/uploads/gallery', max_size=(1200, 800), quality=85)
    
    # Сжать все фото номеров
    compress_folder('static/uploads/rooms', max_size=(1000, 700), quality=80)
    
    print("\n🎉 Все фото сжаты!")