# app.py — ПОЛНАЯ БЕЗОПАСНАЯ ВЕРСИЯ С ПОЛЕМ order + PostgreSQL
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from PIL import Image
import os
import re
import uuid
import logging
from dotenv import load_dotenv
from flask_wtf.csrf import generate_csrf
from flask import send_from_directory

# Загружаем переменные из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================
# 🚀 НАСТРОЙКИ ДЛЯ AMVERA (ПОСТОЯННОЕ ХРАНИЛИЩЕ)
# ============================================================
import sys
print(f"--- ДИАГНОСТИКА ---")
print(f"Значение AMVERA: {os.environ.get('AMVERA')}")
print(f"Значение DB_HOST: {os.environ.get('DB_HOST')}")
print(f"Все переменные (первые 5): {list(os.environ.keys())[:5]}")
print(f"--- КОНЕЦ ДИАГНОСТИКИ ---")
if "AMVERA" in os.environ:
    # На Amvera используем PostgreSQL
    INSTANCE_PATH = os.path.join(os.path.expanduser("~"), "data", "instance")
    UPLOAD_PATH = os.path.join(os.path.expanduser("~"), "data", "uploads")
    
    # PostgreSQL подключение
    DB_USER = os.environ.get('DB_USER', 'postgres').strip()
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '').strip()
    DB_HOST = os.environ.get('DB_HOST', 'localhost').strip()
    DB_PORT = os.environ.get('DB_PORT', '5432').strip()
    DB_NAME = os.environ.get('DB_NAME', 'baikal').strip()
    # ДОБАВИТЬ ЭТУ ДИАГНОСТИКУ:
    print(f"ИМЯ БАЗЫ (КАК ЕЁ ВИДИТ PYTHON): '{DB_NAME}'")
    # ------------------------------------------

    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
else:
    # Локальная разработка — SQLite
    INSTANCE_PATH = "instance"
    UPLOAD_PATH = "static/uploads"
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///baikal.db')

# Создаём папки
os.makedirs(INSTANCE_PATH, exist_ok=True)
os.makedirs(UPLOAD_PATH, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_PATH, 'gallery'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_PATH, 'rooms'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_PATH, 'documents'), exist_ok=True)

# ============================================================
# БЕЗОПАСНАЯ КОНФИГУРАЦИЯ
# ============================================================
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_PATH
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB
app.config['MAX_PHOTOS'] = 20
app.config['MAX_PDF_SIZE'] = 10 * 1024 * 1024  # 10 MB
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# БЕЗОПАСНЫЕ КУКИ (с поддержкой HTTP и HTTPS)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_PATH'] = '/'

# Секретный ключ для доступа к админ-панели (храните в .env)
ADMIN_SECRET_KEY = os.environ.get('ADMIN_SECRET_KEY', 'my-super-secret-key-2026')
ADMIN_PATH = os.environ.get('ADMIN_PATH', '/control-panel')
# ✅ ДОБАВЬТЕ ЭТУ ДИАГНОСТИКУ
print(f"ADMIN_PATH: {ADMIN_PATH}")
print(f"ADMIN_SECRET_KEY (первые 5 символов): {ADMIN_SECRET_KEY[:5]}...")
# ⚡ КЛЮЧЕВОЕ: автоматическое определение протокола
@app.before_request
def set_secure_cookie():
    """Автоматически устанавливает SESSION_COOKIE_SECURE в зависимости от протокола"""
    forwarded_proto = request.headers.get('X-Forwarded-Proto', '')
    if forwarded_proto == 'https' or request.is_secure:
        app.config['SESSION_COOKIE_SECURE'] = True
    else:
        app.config['SESSION_COOKIE_SECURE'] = False

# CSRF-защита
csrf = CSRFProtect(app)


# Проверка SECRET_KEY
if not os.environ.get('SECRET_KEY'):
    logger.warning("SECRET_KEY не установлен в .env! Используется временный ключ.")

# Пароль админа с хешированием
ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get('ADMIN_PASSWORD', 'adm1n1214')
)

db = SQLAlchemy(app)

@app.template_filter('pluralize')
def pluralize(count, one, few, many):
    """
    Универсальное склонение слов для русского языка
    
    Аргументы:
        count (int): число
        one (str): форма для 1 (например, 'гость')
        few (str): форма для 2-4 (например, 'гостя')
        many (str): форма для 5-20 (например, 'гостей')
    
    Пример:
        {{ 1 | pluralize('гость', 'гостя', 'гостей') }} → 1 гость
        {{ 2 | pluralize('гость', 'гостя', 'гостей') }} → 2 гостя
        {{ 5 | pluralize('гость', 'гостя', 'гостей') }} → 5 гостей
    """
    if count % 100 in (11, 12, 13, 14):
        return f"{count} {many}"
    
    last_digit = count % 10
    if last_digit == 1:
        return f"{count} {one}"
    elif last_digit in (2, 3, 4):
        return f"{count} {few}"
    else:
        return f"{count} {many}"

# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============

def transliterate(text):
    """Транслитерация русского текста в латиницу"""
    if not text:
        return ''
    text = text.lower()
    replacements = [
        ('а', 'a'), ('б', 'b'), ('в', 'v'), ('г', 'g'), ('д', 'd'), ('е', 'e'), ('ё', 'yo'),
        ('ж', 'zh'), ('з', 'z'), ('и', 'i'), ('й', 'y'), ('к', 'k'), ('л', 'l'), ('м', 'm'),
        ('н', 'n'), ('о', 'o'), ('п', 'p'), ('р', 'r'), ('с', 's'), ('т', 't'), ('у', 'u'),
        ('ф', 'f'), ('х', 'h'), ('ц', 'ts'), ('ч', 'ch'), ('ш', 'sh'), ('щ', 'sch'),
        ('ъ', ''), ('ы', 'y'), ('ь', ''), ('э', 'e'), ('ю', 'yu'), ('я', 'ya'),
        (' ', '-'), ('_', '-')
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    text = re.sub(r'[^a-z0-9-]', '', text)
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    return text


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    """Проверка расширения файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_image(file):
    """Проверка, что файл является изображением (через Pillow)"""
    if not file:
        return False
    if not allowed_file(file.filename):
        return False
    try:
        img = Image.open(file)
        img.verify()
        file.seek(0)
        return True
    except Exception as e:
        logger.error(f"Ошибка валидации изображения: {e}")
        return False


def secure_filepath(base_path, filename):
    """Предотвращает path traversal"""
    safe_filename = secure_filename(filename)
    if not safe_filename:
        safe_filename = f"file_{uuid.uuid4().hex}"
    full_path = os.path.abspath(os.path.join(base_path, safe_filename))
    if not full_path.startswith(os.path.abspath(base_path)):
        raise ValueError("Path traversal detected")
    return full_path


def save_photo(file, folder='gallery', max_size=(1200, 800), quality=85):
    """
    Сохраняет фото с автоматическим сжатием и изменением размера.
    
    Аргументы:
        file: файл из request.files
        folder: папка для сохранения (gallery, rooms, features)
        max_size: максимальный размер (ширина, высота)
        quality: качество JPEG (1-100, 85 оптимально)
    """
    import io
    
    if not validate_image(file):
        raise ValueError("Файл не является допустимым изображением")
    
    # Открываем изображение
    img = Image.open(file)
    
    # Конвертируем в RGB (для JPEG)
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGB')
    
    # Уменьшаем размер, если изображение больше max_size
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Сохраняем во временный буфер с сжатием
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True, progressive=True)
    buffer.seek(0)
    
    # Генерируем имя файла
    safe_name = secure_filename(file.filename)
    filename = f"{folder}_{uuid.uuid4().hex}.jpg"
    filepath = secure_filepath(os.path.join(app.config['UPLOAD_FOLDER'], folder), filename)
    
    # Сохраняем сжатое изображение
    with open(filepath, 'wb') as f:
        f.write(buffer.getvalue())
    
    if "AMVERA" in os.environ:
        return f"/uploads/{folder}/{os.path.basename(filepath)}"
    else:
        return f"/static/uploads/{folder}/{os.path.basename(filepath)}"


def admin_required(f):
    """Декоратор для защиты админ-маршрутов с проверкой сессии"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('admin_login'))
        
        # Проверка времени сессии (8 часов)
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                last_activity_dt = datetime.fromisoformat(last_activity)
                if datetime.now(timezone.utc) - last_activity_dt > timedelta(hours=8):
                    session.clear()
                    flash('Сессия истекла. Войдите снова.', 'warning')
                    return redirect(url_for('admin_login'))
            except (ValueError, TypeError):
                session.clear()
                return redirect(url_for('admin_login'))
        
        # Обновляем время активности
        session['last_activity'] = datetime.now(timezone.utc).isoformat()
        return f(*args, **kwargs)
    return decorated_function


def update_last_activity():
    """Обновляет время последней активности в сессии"""
    session['last_activity'] = datetime.now(timezone.utc).isoformat()


# ============== МОДЕЛИ ==============

class RoomCategory(db.Model):
    """Категория номера"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True)
    description = db.Column(db.Text)
    rooms = db.relationship('Room', backref='category_ref', lazy=True)

    def __repr__(self):
        return self.name


class Room(db.Model):
    """Номер"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True)
    category_id = db.Column(db.Integer, db.ForeignKey('room_category.id'))
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    capacity = db.Column(db.Integer)
    main_photo = db.Column(db.String(500))
    amenities = db.Column(db.Text)
    is_available = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # ✅ ДОБАВЛЕНО: поле для ручной сортировки
    order = db.Column(db.Integer, default=0)

    category = db.relationship('RoomCategory', backref='room_list', overlaps="category_ref,rooms")

    def __init__(self, *args, **kwargs):
        super(Room, self).__init__(*args, **kwargs)
        if not self.slug:
            self.generate_slug()

    def generate_slug(self):
        category_slug = ''
        if self.category_id:
            category = RoomCategory.query.get(self.category_id)
            if category:
                category_slug = category.slug + '-'
        name_slug = transliterate(self.name)
        base_slug = category_slug + name_slug
        slug = base_slug
        counter = 1
        while Room.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        self.slug = slug

    def __repr__(self):
        return self.name


class GalleryPhoto(db.Model):
    """Фото для галереи базы отдыха"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, default="Фото")
    image = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return self.title


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), default="Байкал-центр")
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    phone2 = db.Column(db.String(20))
    email = db.Column(db.String(100))

    def __repr__(self):
        return self.name


class BookingRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    check_in = db.Column(db.Date)
    check_out = db.Column(db.Date)
    guests = db.Column(db.Integer)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_processed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"Заявка от {self.name}"


class RoomImage(db.Model):
    """Дополнительные фото номера"""
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id', ondelete='CASCADE'))
    image = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(200))
    order = db.Column(db.Integer, default=0)
    is_main = db.Column(db.Boolean, default=False)
    room = db.relationship('Room', backref='images')

    def __repr__(self):
        return f"Фото #{self.id}"


class Document(db.Model):
    """PDF-документы для подвала сайта"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    icon = db.Column(db.String(50), default='fa-file-pdf')
    is_published = db.Column(db.Boolean, default=True)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return self.title


# ============== АДМИН-ПАНЕЛЬ ==============

# ⭐ СКРЫТАЯ АДМИН-ПАНЕЛЬ
@app.route('/admin')
def admin_hidden():
    """Возвращаем 404, чтобы скрыть существование админки"""
    abort(404)

# ⭐ РЕАЛЬНЫЙ ВХОД В АДМИНКУ (через секретный ключ)
@app.route(ADMIN_PATH)
def admin_access():
    """Доступ к админ-панели через секретный ключ в URL"""
    secret = request.args.get('secret')
    if secret != ADMIN_SECRET_KEY:
        abort(404)
    return redirect(url_for('admin_login'))

# ⭐ ОСНОВНОЙ МАРШРУТ АДМИНКИ
@app.route('/admin-panel')
@admin_required
def admin_index():
    update_last_activity()
    rooms_count = Room.query.count()
    available_rooms = Room.query.filter_by(is_available=True).count()
    categories_count = RoomCategory.query.count()
    gallery_count = GalleryPhoto.query.count()
    documents_count = Document.query.count()
    return render_template('admin/dashboard.html',
                           rooms_count=rooms_count,
                           available_rooms=available_rooms,
                           categories_count=categories_count,
                           gallery_count=gallery_count,
                           documents_count=documents_count,
                           now=datetime.now(timezone.utc))


import logging

@app.route('/admin/login', methods=['GET', 'POST'])
@csrf.exempt
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        
        if not password:
            flash('Введите пароль!', 'warning')
            return render_template('admin/login.html')
        
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.permanent = True
            session['admin_logged_in'] = True
            session['last_activity'] = datetime.now(timezone.utc).isoformat()
            session.modified = True
            flash('Вход выполнен!', 'success')
            return redirect(url_for('admin_index'))
        else:
            flash('Неверный пароль!', 'danger')
    
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('admin_login'))


# ============== УПРАВЛЕНИЕ ГАЛЕРЕЕЙ ==============

@app.route('/admin/gallery')
@admin_required
def admin_gallery():
    update_last_activity()
    photos = GalleryPhoto.query.order_by(GalleryPhoto.order).all()
    return render_template('admin/gallery.html', photos=photos)


@app.route('/admin/gallery/add', methods=['GET', 'POST'])
@admin_required
def admin_add_gallery_photo():
    update_last_activity()
    if request.method == 'POST':
        photos_count = GalleryPhoto.query.count()
        order = photos_count + 1
        photos_added = 0

        if 'photos' in request.files:
            files = request.files.getlist('photos')
            
            # Проверка лимита
            if len(files) > app.config['MAX_PHOTOS']:
                flash(f'Можно загрузить не более {app.config["MAX_PHOTOS"]} фото за раз', 'danger')
                return redirect(url_for('admin_gallery'))
            
            for file in files:
                if file and file.filename and validate_image(file):
                    try:
                        image_url = save_photo(file, 'gallery')
                        photo = GalleryPhoto(title="Фото", image=image_url, order=order, is_active=True)
                        db.session.add(photo)
                        order += 1
                        photos_added += 1
                    except ValueError as e:
                        flash(f'Ошибка: {e}', 'danger')

        image_urls = request.form.get('image_urls', '').strip()
        if image_urls:
            for url in image_urls.split('\n'):
                url = url.strip()
                if url and (url.startswith('http://') or url.startswith('https://')):
                    photo = GalleryPhoto(title="Фото", image=url, order=order, is_active=True)
                    db.session.add(photo)
                    order += 1
                    photos_added += 1

        db.session.commit()
        if photos_added > 0:
            flash(f'Добавлено фото: {photos_added} шт.', 'success')
        else:
            flash('Не выбрано ни одного фото', 'warning')
        return redirect(url_for('admin_gallery'))

    return render_template('admin/add_gallery_photo.html')


@app.route('/admin/gallery/<int:id>/delete', methods=['GET', 'POST'])
@admin_required
def admin_delete_gallery_photo(id):
    update_last_activity()
    photo = GalleryPhoto.query.get_or_404(id)
    if photo.image and photo.image.startswith('/static/uploads/'):
        try:
            relative_path = photo.image.replace('/static/uploads/', '').lstrip('/')
            safe_path = secure_filepath(os.path.join(app.config['UPLOAD_FOLDER']), relative_path)
            if os.path.exists(safe_path):
                os.remove(safe_path)
        except (ValueError, OSError) as e:
            logger.error(f"Ошибка удаления файла галереи: {e}")

    db.session.delete(photo)
    db.session.commit()

    photos = GalleryPhoto.query.order_by(GalleryPhoto.order).all()
    for i, p in enumerate(photos, 1):
        p.order = i
    db.session.commit()

    flash('Фото удалено!', 'success')
    return redirect(url_for('admin_gallery'))


@app.route('/admin/gallery/<int:id>/move/<direction>')
@admin_required
def admin_move_gallery_photo(id, direction):
    update_last_activity()
    photo = GalleryPhoto.query.get_or_404(id)
    photos = GalleryPhoto.query.order_by(GalleryPhoto.order).all()
    current_index = next((i for i, p in enumerate(photos) if p.id == id), None)

    if current_index is not None:
        if direction == 'up' and current_index > 0:
            photos[current_index].order, photos[current_index - 1].order = \
                photos[current_index - 1].order, photos[current_index].order
        elif direction == 'down' and current_index < len(photos) - 1:
            photos[current_index].order, photos[current_index + 1].order = \
                photos[current_index + 1].order, photos[current_index].order
        db.session.commit()

    photos = GalleryPhoto.query.order_by(GalleryPhoto.order).all()
    for i, p in enumerate(photos, 1):
        p.order = i
    db.session.commit()

    return redirect(url_for('admin_gallery'))


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_PATH, filename)
    
# ============== УПРАВЛЕНИЕ НОМЕРАМИ ==============

@app.route('/admin/rooms')
@admin_required
def admin_rooms():
    update_last_activity()
    category_id = request.args.get('category', '')
    query = Room.query
    selected_category = None
    if category_id and category_id.isdigit():
        category_id = int(category_id)
        selected_category = category_id
        query = query.filter_by(category_id=category_id)
    
    # ✅ ИЗМЕНЕНО: сортировка по полю order, затем по дате создания
    rooms = query.order_by(Room.order.asc(), Room.created_at.desc()).all()
    
    categories = RoomCategory.query.all()
    total_count = Room.query.count()
    return render_template('admin/rooms.html', rooms=rooms, categories=categories,
                           selected_category=selected_category, total_count=total_count)


@app.route('/admin/rooms/add', methods=['GET', 'POST'])
@admin_required
def admin_add_room():
    update_last_activity()
    categories = RoomCategory.query.all()
    
    # ✅ ДОБАВЛЕНО: количество номеров для подсказки в форме
    rooms_count = Room.query.count()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Название обязательно!', 'danger')
            return render_template('admin/add_room.html', categories=categories, rooms_count=rooms_count)
        try:
            price = float(request.form.get('price', 0))
            capacity = int(request.form.get('capacity', 1))
        except (ValueError, TypeError):
            flash('Некорректная цена или вместимость!', 'danger')
            return render_template('admin/add_room.html', categories=categories, rooms_count=rooms_count)

        # ✅ ДОБАВЛЕНО: получение значения order из формы
        try:
            order = int(request.form.get('order', 0))
        except (ValueError, TypeError):
            order = 0

        room = Room(
            name=name,
            category_id=request.form.get('category_id'),
            description=request.form.get('description', '').strip(),
            price=price,
            capacity=capacity,
            is_available=request.form.get('is_available') == '1',
            order=order  # ✅ ДОБАВЛЕНО
        )
        db.session.add(room)
        db.session.flush()

        main_photo_index = request.form.get('main_photo_index', '-1')
        if 'gallery_photos' in request.files:
            files = request.files.getlist('gallery_photos')
            order_photo = 0
            for i, file in enumerate(files):
                if file and file.filename and validate_image(file):
                    try:
                        image_url = save_photo(file, 'gallery')
                        is_main = (str(i) == main_photo_index)
                        img = RoomImage(room_id=room.id, image=image_url, order=order_photo, is_main=is_main)
                        db.session.add(img)
                        if is_main:
                            room.main_photo = image_url
                        order_photo += 1
                    except ValueError as e:
                        flash(f'Ошибка загрузки фото: {e}', 'danger')

        db.session.commit()
        flash('Номер добавлен!', 'success')
        return redirect(url_for('admin_rooms'))

    return render_template('admin/add_room.html', categories=categories, rooms_count=rooms_count)


@app.route('/admin/rooms/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_room(id):
    update_last_activity()
    room = Room.query.get_or_404(id)
    categories = RoomCategory.query.all()
    
    if request.method == 'POST':
        room.name = request.form.get('name', '').strip()
        room.category_id = request.form.get('category_id')
        room.description = request.form.get('description', '').strip()
        try:
            room.price = float(request.form.get('price', 0))
            room.capacity = int(request.form.get('capacity', 1))
        except (ValueError, TypeError):
            flash('Некорректная цена или вместимость!', 'danger')
            return render_template('admin/edit_room.html', room=room, categories=categories)
        
        # ✅ ДОБАВЛЕНО: получение значения order из формы
        try:
            room.order = int(request.form.get('order', 0))
        except (ValueError, TypeError):
            room.order = 0
        
        room.is_available = request.form.get('is_available') == '1'

        # Удаление отмеченных фото
        delete_ids = request.form.get('delete_images', '')
        if delete_ids:
            for img_id in delete_ids.split(','):
                if img_id and img_id.isdigit():
                    image = RoomImage.query.get(int(img_id))
                    if image:
                        if image.image and image.image.startswith('/static/uploads/'):
                            try:
                                relative_path = image.image.replace('/static/uploads/', '').lstrip('/')
                                safe_path = secure_filepath(os.path.join(app.config['UPLOAD_FOLDER']), relative_path)
                                if os.path.exists(safe_path):
                                    os.remove(safe_path)
                            except (ValueError, OSError) as e:
                                logger.error(f"Ошибка удаления файла: {e}")
                        db.session.delete(image)

        # Сброс главного фото
        RoomImage.query.filter_by(room_id=room.id).update({'is_main': False})
        main_photo_set = False

        # Главное из существующих
        new_main = request.form.get('new_main_image_id', '')
        if new_main.startswith('existing_'):
            img_id_str = new_main.replace('existing_', '')
            if img_id_str.isdigit():
                image = RoomImage.query.get(int(img_id_str))
                if image:
                    image.is_main = True
                    room.main_photo = image.image
                    main_photo_set = True

        # Новые фото
        new_main_index = request.form.get('new_main_index')
        if 'new_gallery_photos' in request.files:
            files = request.files.getlist('new_gallery_photos')
            current_order = RoomImage.query.filter_by(room_id=room.id).count()
            for i, file in enumerate(files):
                if file and file.filename and validate_image(file):
                    try:
                        image_url = save_photo(file, 'gallery')
                        is_main = (str(i) == new_main_index) and not main_photo_set
                        img = RoomImage(room_id=room.id, image=image_url, order=current_order + i, is_main=is_main)
                        db.session.add(img)
                        if is_main:
                            room.main_photo = image_url
                            main_photo_set = True
                    except ValueError as e:
                        flash(f'Ошибка загрузки фото: {e}', 'danger')

        db.session.commit()
        flash('Номер обновлён!', 'success')
        return redirect(url_for('admin_rooms'))

    return render_template('admin/edit_room.html', room=room, categories=categories)


@app.route('/admin/rooms/<int:id>/delete')
@admin_required
def admin_delete_room(id):
    update_last_activity()
    room = Room.query.get_or_404(id)
    for image in room.images:
        if image.image and image.image.startswith('/static/uploads/'):
            try:
                relative_path = image.image.replace('/static/uploads/', '').lstrip('/')
                safe_path = secure_filepath(os.path.join(app.config['UPLOAD_FOLDER']), relative_path)
                if os.path.exists(safe_path):
                    os.remove(safe_path)
            except (ValueError, OSError) as e:
                logger.error(f"Ошибка удаления файла: {e}")
    db.session.delete(room)
    db.session.commit()
    flash('Номер удалён!', 'success')
    return redirect(url_for('admin_rooms'))

    
# ============== УПРАВЛЕНИЕ КАТЕГОРИЯМИ ==============

@app.route('/admin/categories')
@admin_required
def admin_categories():
    update_last_activity()
    categories = RoomCategory.query.order_by(RoomCategory.name).all()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/add', methods=['GET', 'POST'])
@admin_required
def admin_add_category():
    update_last_activity()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Название обязательно!', 'danger')
            return render_template('admin/add_category.html')
        slug = transliterate(name)
        existing = RoomCategory.query.filter_by(slug=slug).first()
        if existing:
            counter = 1
            while RoomCategory.query.filter_by(slug=f"{slug}-{counter}").first():
                counter += 1
            slug = f"{slug}-{counter}"
        category = RoomCategory(name=name, slug=slug, description=request.form.get('description', '').strip())
        db.session.add(category)
        db.session.commit()
        flash('Категория добавлена!', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/add_category.html')


@app.route('/admin/categories/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_category(id):
    update_last_activity()
    category = RoomCategory.query.get_or_404(id)
    if request.method == 'POST':
        category.name = request.form.get('name', '').strip()
        category.description = request.form.get('description', '').strip()
        db.session.commit()
        flash('Категория обновлена!', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/edit_category.html', category=category)


@app.route('/admin/categories/<int:id>/delete', methods=['GET', 'POST'])
@admin_required
def admin_delete_category(id):
    update_last_activity()
    category = RoomCategory.query.get_or_404(id)

    if request.method == 'POST':
    
        if category.rooms:
            flash(f'Нельзя удалить: в категории {len(category.rooms)} номеров!', 'danger')
        else:
            db.session.delete(category)
            db.session.commit()
            flash('Категория удалена!', 'success')
    
    return redirect(url_for('admin_categories'))


# ============== ЗАЯВКИ ==============

@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    update_last_activity()
    bookings = BookingRequest.query.order_by(BookingRequest.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings)


@app.route('/admin/bookings/<int:id>/process')
@admin_required
def admin_process_booking(id):
    update_last_activity()
    booking = BookingRequest.query.get_or_404(id)
    booking.is_processed = True
    db.session.commit()
    flash('Заявка обработана!', 'success')
    return redirect(url_for('admin_bookings'))


# ============== УПРАВЛЕНИЕ PDF-ДОКУМЕНТАМИ ==============

@app.route('/admin/documents')
@admin_required
def admin_documents():
    update_last_activity()
    documents = Document.query.order_by(Document.order).all()
    return render_template('admin/documents.html', documents=documents)


@app.route('/admin/documents/add', methods=['GET', 'POST'])
@admin_required
def admin_add_document():
    update_last_activity()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Название обязательно!', 'danger')
            return render_template('admin/add_document.html')
        
        if 'pdf_file' not in request.files:
            flash('Выберите PDF-файл!', 'danger')
            return render_template('admin/add_document.html')
        
        file = request.files['pdf_file']
        if not file or not file.filename:
            flash('Выберите PDF-файл!', 'danger')
            return render_template('admin/add_document.html')
        
        # Проверка MIME-типа
        if file.mimetype != 'application/pdf':
            flash('Файл должен быть PDF!', 'danger')
            return render_template('admin/add_document.html')
        
        # Проверка расширения
        ext = file.filename.rsplit('.', 1)[-1].lower()
        if ext != 'pdf':
            flash('Только PDF!', 'danger')
            return render_template('admin/add_document.html')
        
        # Проверка размера файла
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > app.config['MAX_PDF_SIZE']:
            flash(f'Файл слишком большой! Максимум {app.config["MAX_PDF_SIZE"] // (1024 * 1024)} МБ', 'danger')
            return render_template('admin/add_document.html')
        
        safe_name = secure_filename(file.filename)
        filename = f"doc_{uuid.uuid4().hex}.pdf"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        
        document = Document(
            title=title,
            file_path=f"/static/uploads/documents/{filename}",
            is_published=request.form.get('is_published') == '1',
            order=int(request.form.get('order', 0))
        )
        db.session.add(document)
        db.session.commit()
        
        flash('PDF загружен!', 'success')
        return redirect(url_for('admin_documents'))
    
    return render_template('admin/add_document.html')


@app.route('/admin/documents/<int:id>/delete', methods=['GET', 'POST'])
@admin_required
def admin_delete_document(id):
    update_last_activity()
    document = Document.query.get_or_404(id)
    
    # Безопасное удаление файла
    if document.file_path.startswith('/static/uploads/documents/'):
        try:
            relative_path = document.file_path.replace('/static/uploads/', '').lstrip('/')
            safe_path = secure_filepath(os.path.join(app.config['UPLOAD_FOLDER']), relative_path)
            if os.path.exists(safe_path):
                os.remove(safe_path)
        except (ValueError, OSError) as e:
            logger.error(f"Ошибка удаления PDF: {e}")
    
    db.session.delete(document)
    db.session.commit()
    
    flash('Документ удалён!', 'success')
    return redirect(url_for('admin_documents'))


# ============== ПУБЛИЧНЫЕ МАРШРУТЫ ==============

@app.route('/')
def home():
    featured_rooms = Room.query.filter_by(is_available=True, is_featured=True).limit(3).all()
    if len(featured_rooms) < 3:
        featured_rooms = Room.query.filter_by(is_available=True).limit(3).all()
    
    categories = RoomCategory.query.all()
    gallery_photos = GalleryPhoto.query.filter_by(is_active=True).order_by(GalleryPhoto.order).all()
    
    return render_template('home.html', 
                          rooms=featured_rooms, 
                          categories=categories,
                          gallery_photos=gallery_photos)


@app.route('/rooms')
def room_list():
    category_slug = request.args.get('category', '')
    query = Room.query.filter_by(is_available=True)
    selected_category = None
    if category_slug:
        selected_category = RoomCategory.query.filter_by(slug=category_slug).first()
        if selected_category:
            query = query.filter_by(category_id=selected_category.id)
    
    # ✅ ИЗМЕНЕНО: сортировка по полю order, затем по цене
    rooms = query.order_by(Room.order.asc(), Room.price.asc()).all()
    
    categories = RoomCategory.query.all()
    total_rooms_count = Room.query.filter_by(is_available=True).count()
    return render_template('rooms.html', rooms=rooms, categories=categories,
                           selected_category=selected_category, total_rooms_count=total_rooms_count)


@app.route('/room/<slug>')
def room_detail(slug):
    if not re.match(r'^[a-z0-9-]+$', slug):
        return "Not Found", 404
    room = Room.query.filter_by(slug=slug, is_available=True).first_or_404()
    similar_rooms = Room.query.filter(
        Room.category_id == room.category_id,
        Room.id != room.id,
        Room.is_available == True
    ).limit(3).all()
    return render_template('room_detail.html', room=room, similar_rooms=similar_rooms)


@app.context_processor
def inject_models():
    """Делает модели доступными во всех шаблонах"""
    return {
        'Document': Document,
        'datetime': datetime,
        'csrf_token': generate_csrf
    }

# ============== ЗАПУСК ==============

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Contact.query.first():
            contact = Contact(
                name="Байкал-центр",
                address="Республика Бурятия, пос. Горячинск, ул. Октябрьская, 15Б",
                phone="+7 (924) 353-32-64",
                phone2="+7 (924) 653-97-50",
            )
            db.session.add(contact)
        db.session.commit()
        print("✅ База данных готова!")

    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    print("🏔️ Байкал-центр запущен!")
    print("📍 http://127.0.0.1:5000")
    print("🔧 http://127.0.0.1:5000/admin")
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
