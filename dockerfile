FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Set Flask app for CLI commands used in entrypoint
ENV FLASK_APP=run.py

# Ensure entrypoint script is executable
RUN chmod +x /app/docker-entrypoint.sh

# Run migrations on startup, then launch Gunicorn
ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
