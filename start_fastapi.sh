#!/bin/bash

echo "🚀 Starting Frames Viewer with FastAPI..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed"
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Start the FastAPI backend in the background
echo "🔧 Starting FastAPI backend..."
python server_fastapi.py &
BACKEND_PID=$!

# Wait longer for backend to start (TensorFlow model loading takes time)
echo "⏳ Waiting for backend to start (this may take a minute for TensorFlow model loading)..."
sleep 30

# Check if backend started successfully with multiple retries
echo "🔍 Checking if backend is ready..."
for i in {1..10}; do
    if curl -s http://localhost:8000/api/health > /dev/null; then
        echo "✅ FastAPI backend is running at http://localhost:8000"
        echo "📚 API documentation available at http://localhost:8000/docs"
        break
    else
        echo "⏳ Still waiting for backend to start... (attempt $i/10)"
        sleep 5
    fi
done

if ! curl -s http://localhost:8000/api/health > /dev/null; then
    echo "❌ Error: FastAPI backend failed to start after multiple attempts"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Start the React frontend
echo "🎨 Starting React frontend..."
npm start

# Cleanup function
cleanup() {
    echo "🛑 Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Wait for background process
wait $BACKEND_PID 