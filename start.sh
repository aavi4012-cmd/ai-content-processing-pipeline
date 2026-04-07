#!/bin/bash

# Start Celery worker in the background
echo "Starting Celery Worker..."
celery -A app.queue.celery_app worker --loglevel=info -P solo &

# Start FastAPI application
echo "Starting FastAPI App..."
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
