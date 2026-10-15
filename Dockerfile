FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TASKLY_DATA_DIR=/data

WORKDIR /srv

# Dependencies first so Docker caches this layer until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

# Run as a normal user, not root; /data is where the database and audio live
RUN useradd --create-home appuser && mkdir /data && chown appuser /data
USER appuser
VOLUME /data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
