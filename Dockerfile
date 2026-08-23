# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Создаём папки для постоянных данных
RUN mkdir -p /data /data/uploads /data/instance

# Открываем порт, который будет использовать приложение
EXPOSE 5000

# Запускаем приложение
CMD ["python", "app.py"]