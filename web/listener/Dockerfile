FROM python:3.12-slim
WORKDIR /app
# tzdata so the TZ env var (e.g. Europe/London) resolves to real local time.
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY parser.py bambu_ftp.py listener.py ./
# -u = unbuffered so logs show up immediately in `docker compose logs`
CMD ["python", "-u", "listener.py"]
