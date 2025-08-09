#!/bin/bash
# Setup script for Redis + Celery + Flower

echo "🚀 Setting up Redis + Celery + Flower environment"
echo "=================================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Redis is installed
if command_exists redis-server; then
    echo "✅ Redis is already installed"
else
    echo "📦 Installing Redis..."
    if command_exists apt; then
        sudo apt update && sudo apt install -y redis-server
    elif command_exists yum; then
        sudo yum install -y redis
    elif command_exists brew; then
        brew install redis
    else
        echo "❌ Could not install Redis. Please install manually."
        exit 1
    fi
fi

# Start Redis if not running
if ! pgrep -x "redis-server" > /dev/null; then
    echo "🔄 Starting Redis server..."
    redis-server --daemonize yes
    sleep 2
else
    echo "✅ Redis server is already running"
fi

# Test Redis connection
if redis-cli ping | grep -q PONG; then
    echo "✅ Redis is responding"
else
    echo "❌ Redis is not responding"
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "🎉 Setup complete! Now you can:"
echo "1. Start video interpolation worker: ./start_interpolation_worker.sh"
echo "2. Start Flower monitoring: python -m flower --broker=redis://localhost:6379/0 --port=5555 &"
echo "3. Test interpolation: python test_interpolation.py"
echo "4. Open browser: http://localhost:5555 (Flower UI)"
echo ""
echo "📚 Video Interpolation Server:"
echo "- Submit jobs: from video_interpolation_server import interpolate_video_frames"
echo "- Monitor progress in Flower dashboard"
echo "- Integrate with FastAPI for production use" 