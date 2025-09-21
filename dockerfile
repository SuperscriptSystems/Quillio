FROM python:3.13-slim

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
RUN pip install poetry
RUN poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock* ./
RUN poetry install --only=main --no-interaction --no-ansi --no-root

ENV PATH=/root/.local/bin:$PATH

COPY . .

# Ensure line endings are correct and make script executable
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh

# Set environment variables
ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Expose the port the app runs on
EXPOSE 8000

# Run migrations and start Gunicorn
ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
