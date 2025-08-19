FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["gunicorn", "run:app", "--workers", "3", "--bind", "0.0.0.0:8000"]
