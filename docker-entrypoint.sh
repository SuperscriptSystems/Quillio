#!/bin/bash
set -e

# Ensure Flask knows where the app is
export FLASK_APP=${FLASK_APP:-run.py}

# Install any missing dependencies
echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

# Wait for the database to be ready
echo "Waiting for database to be ready..."
until nc -z -v -w30 ${DB_HOST:-db} ${DB_PORT:-5432}
do
  echo "Waiting for database connection..."
  sleep 5
done

# Run database migrations
echo "Running database migrations..."
flask db upgrade

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn --workers ${GUNICORN_WORKERS:-3} --bind 0.0.0.0:8000 run:app
