FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# torch solo CPU (mucho más liviano que la versión con CUDA)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
COPY src ./src
COPY db ./db
COPY models ./models
# /data escribible por cualquier usuario; aquí se guardan la base de datos y las capturas
RUN mkdir -p /data && chmod 777 /data
# puerto por defecto 7860; los servicios en la nube lo sobrescriben con $PORT
ENV DATA_DIR=/data PYTHONUNBUFFERED=1 PORT=7860 YOLO_CONFIG_DIR=/tmp/ultralytics
WORKDIR /app/src
# El puerto llega en $PORT. 1 worker: el modelo ocupa memoria; 4 hilos para atender varias subidas.
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 180
