FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY parser.py listener.py ./
# -u = unbuffered so logs show up immediately in `docker compose logs`
CMD ["python", "-u", "listener.py"]
