#!/bin/sh
set -e

# Set default environment variables
export FLASK_APP=${FLASK_APP:-run.py}
export FLASK_ENV=${FLASK_ENV:-production}

# Wait for database to be available (if needed)
# Example for PostgreSQL:
# while ! nc -z $DB_HOST $DB_PORT; do
#   echo "Waiting for PostgreSQL..."
#   sleep 1
# done

echo "Running database migrations..."
flask db upgrade

# Create necessary directories
mkdir -p /app/instance

# Set proper permissions
chmod -R 755 /app/instance

# Start Gunicorn
exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-4} \
    --worker-class gthread \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level ${GUNICORN_LOG_LEVEL:-info} \
    --worker-tmp-dir /dev/shm \
    run:app
