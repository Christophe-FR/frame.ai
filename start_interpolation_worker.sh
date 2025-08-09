#!/bin/bash
# Start Video Interpolation Worker

echo "🚀 Starting Video Interpolation Worker"
echo "======================================"

# Check if Redis is running
if ! pgrep -x "redis-server" > /dev/null; then
    echo "🔄 Starting Redis server..."
    redis-server --daemonize yes
    sleep 2
fi

if redis-cli ping | grep -q PONG; then
    echo "✅ Redis is running"
else
    echo "❌ Redis failed to start"
    exit 1
fi

echo "🎬 Starting Celery worker for video interpolation..."
echo "📊 Monitor in Flower: http://localhost:5555"
echo "🔧 Press Ctrl+C to stop"
echo ""

# Start the Celery worker with solo pool (avoids CUDA/TensorFlow fork issues)
# Listen to both default celery queue and interpolation queue
celery -A video_interpolation_server worker --loglevel=info --queues=celery,interpolation --pool=solo --concurrency=1 