# ConvocaUR API — imagen para Fly.io
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt .
RUN pip install --upgrade pip && pip install -r requirements-api.txt

# Código
COPY backend ./backend
COPY src ./src

# Datos necesarios para servir el dashboard (precomputados)
COPY data/processed ./data/processed
COPY data/raw/urosario ./data/raw/urosario
COPY analisis/secop/salidas_capacidad3 ./analisis/secop/salidas_capacidad3

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --app-dir backend"]
