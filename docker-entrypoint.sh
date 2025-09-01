#!/bin/sh
set -e

# Ensure Flask knows where the app is
export FLASK_APP=${FLASK_APP:-run.py}

echo "Running database migrations..."
flask db upgrade || { echo "Failed to run migrations"; exit 1; }

echo "Starting Gunicorn..."
exec gunicorn run:app --workers ${GUNICORN_WORKERS:-3} --bind 0.0.0.0:8000
