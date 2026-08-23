FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN mkdir -p /data /data/uploads /data/instance
EXPOSE 5000
CMD ["gunicorn", "app:app"]
