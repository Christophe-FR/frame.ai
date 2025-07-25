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

# Wait a moment for backend to start
sleep 3

# Check if backend started successfully
if ! curl -s http://localhost:8000/api/health > /dev/null; then
    echo "❌ Error: FastAPI backend failed to start"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo "✅ FastAPI backend is running at http://localhost:8000"
echo "📚 API documentation available at http://localhost:8000/docs"

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