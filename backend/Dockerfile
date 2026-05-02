# Overtone API — Google Cloud Run (listen on $PORT)
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-impress \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

# Cloud Run sets PORT; keep 8080 as default for local docker run.
CMD ["/bin/sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port \"${PORT:-8080}\""]
