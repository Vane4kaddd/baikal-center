FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data /data/uploads /data/instance
EXPOSE 5000

# Запускаем приложение
CMD ["python", "app.py"]