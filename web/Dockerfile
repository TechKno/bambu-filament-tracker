# --- Stage 1: build the React SPA ---------------------------------------- #
FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci 2>/dev/null || npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime serving API + built SPA --------------------- #
FROM python:3.12-slim
WORKDIR /app

# tzdata so the TZ env var (e.g. Europe/London) resolves to real local time.
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /app/dist ./frontend/dist

ENV FILAMENT_DATA_DIR=/data \
    FILAMENT_STATIC_DIR=/app/frontend/dist \
    PORT=8000
EXPOSE 8000
VOLUME ["/data"]

WORKDIR /app/backend
# Single sync worker keeps JSON reads/writes serialized (this is a one-user app).
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "1", "--timeout", "60", "app:app"]
