#!/bin/bash

echo "Starting FastAPI Backend..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 &

echo "Waiting for Backend to start on port 8000..."
max_retries=30
count=0
while ! curl -s http://localhost:8000/ > /dev/null; do
    sleep 2
    count=$((count + 1))
    if [ $count -ge $max_retries ]; then
        echo "Backend failed to start in time. Printing logs and exiting..."
        exit 1
    fi
    echo "Still waiting for backend ($count/$max_retries)..."
done

echo "Backend is UP! Starting Gradio UI..."
python ui/app.py