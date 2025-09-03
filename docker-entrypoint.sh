#!/usr/bin/env sh
set -e

# Ensure Flask knows where the app is
export FLASK_APP=${FLASK_APP:-run.py}

echo "Running database migrations..."
poetry run flask db upgrade

echo "Starting Gunicorn..."
exec poetry run gunicorn run:app --workers ${GUNICORN_WORKERS:-3} --bind 0.0.0.0:8000
