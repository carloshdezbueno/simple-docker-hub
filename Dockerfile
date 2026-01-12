FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorios
RUN mkdir -p /data && \
    mkdir -p /app/static/uploads

# Copiar el código
COPY . .

# Variables de entorno
ENV DB_PATH=/data/links.db

# Volúmenes
VOLUME /data
VOLUME /app/static/uploads

EXPOSE 5000

CMD ["python", "app.py"]