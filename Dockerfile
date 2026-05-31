FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev gcc pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY backend_python/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/backend_python

ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "-m", "uvicorn", "app_fastapi:app", "--host", "0.0.0.0", "--port", "5000"]
