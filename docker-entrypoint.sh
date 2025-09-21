#!/bin/bash
set -e

# Ensure Flask knows where the app is
export FLASK_APP=${FLASK_APP:-run.py}

# Install any missing dependencies
echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

# Wait for the database to be ready
echo "Waiting for database to be ready..."
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}

# Use Python to check database connection
python3 -c "
import sys
import socket
import time

def is_db_ready(host, port, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (socket.error, socket.timeout):
            print('Waiting for database connection...')
            time.sleep(5)
    return False

if not is_db_ready('$DB_HOST', $DB_PORT):
    print('Error: Could not connect to the database', file=sys.stderr)
    sys.exit(1)
"

echo "Database is ready!"

# Run database migrations
echo "Running database migrations..."
flask db upgrade

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn --workers ${GUNICORN_WORKERS:-3} --bind 0.0.0.0:8000 run:app
