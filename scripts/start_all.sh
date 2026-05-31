#!/bin/bash

# Start Backend
echo "Starting Backend..."
python3 main.py &

# Start Frontend
echo "Starting Frontend..."
if [ -d "frontend" ]; then
    cd frontend
    npm install
    npm run dev &
else
    echo "Frontend directory not found!"
fi

# Wait for background processes
wait
