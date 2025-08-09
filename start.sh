#!/bin/bash

echo "🚀 Starting Frame Interpolation Project"
echo "======================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Waiting for ${service_name} to be ready...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ ${service_name} is ready!${NC}"
            return 0
        fi
        echo -e "${YELLOW}   Attempt $attempt/$max_attempts - waiting...${NC}"
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}❌ ${service_name} failed to start after $max_attempts attempts${NC}"
    return 1
}

# Create necessary directories
echo -e "${BLUE}📁 Creating directories...${NC}"
mkdir -p frames static

# Check if Redis is running
echo -e "${BLUE}🔍 Checking Redis...${NC}"
if ! pgrep -x "redis-server" > /dev/null; then
    echo -e "${YELLOW}🔄 Starting Redis server...${NC}"
    redis-server --daemonize yes
    sleep 2
fi

if redis-cli ping | grep -q PONG; then
    echo -e "${GREEN}✅ Redis is running${NC}"
else
    echo -e "${RED}❌ Redis failed to start${NC}"
    exit 1
fi

# Start FastAPI Backend
echo -e "${BLUE}🖥️  Starting FastAPI Backend...${NC}"
if check_port 8500; then
    echo -e "${YELLOW}⚠️  Port 8500 is in use, using port 8501${NC}"
    PORT=8501
else
    PORT=8500
fi

if [ "$PORT" = "8501" ]; then
    python -c "
import uvicorn
from server_fastapi import app
uvicorn.run(app, host='0.0.0.0', port=8501)
" > logs/fastapi.log 2>&1 &
else
    python server_fastapi.py > logs/fastapi.log 2>&1 &
fi
FASTAPI_PID=$!
echo $FASTAPI_PID > pids/fastapi.pid

# Wait for FastAPI to be ready
if wait_for_service "http://localhost:$PORT/api/health" "FastAPI Backend"; then
    echo -e "${GREEN}✅ FastAPI Backend running on port $PORT (PID: $FASTAPI_PID)${NC}"
else
    echo -e "${RED}❌ FastAPI Backend failed to start${NC}"
    exit 1
fi

# Start Flower (Celery monitoring)
echo -e "${BLUE}🌸 Starting Flower...${NC}"
python -m flower --broker=redis://localhost:6379/0 --port=5555 > logs/flower.log 2>&1 &
FLOWER_PID=$!
echo $FLOWER_PID > pids/flower.pid

# Wait for Flower to be ready
if wait_for_service "http://localhost:5555" "Flower"; then
    echo -e "${GREEN}✅ Flower running on port 5555 (PID: $FLOWER_PID)${NC}"
else
    echo -e "${YELLOW}⚠️  Flower might have issues but continuing...${NC}"
fi

# Start Celery Worker
echo -e "${BLUE}⚙️  Starting Celery Worker...${NC}"
celery -A video_interpolation_server worker --loglevel=info --queues=celery,interpolation --pool=solo --concurrency=1 > logs/celery.log 2>&1 &
CELERY_PID=$!
echo $CELERY_PID > pids/celery.pid
echo -e "${GREEN}✅ Celery Worker started (PID: $CELERY_PID)${NC}"

# Start React Frontend
echo -e "${BLUE}⚛️  Starting React Frontend...${NC}"
PORT=3500 npm start > logs/react.log 2>&1 &
REACT_PID=$!
echo $REACT_PID > pids/react.pid

# Wait for React to be ready
if wait_for_service "http://localhost:3500" "React Frontend"; then
    echo -e "${GREEN}✅ React Frontend running on port 3500 (PID: $REACT_PID)${NC}"
else
    echo -e "${RED}❌ React Frontend failed to start${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 All services started successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Service URLs:${NC}"
echo -e "   Frontend:     ${GREEN}http://localhost:3500${NC}"
echo -e "   Backend API:  ${GREEN}http://localhost:$PORT${NC}"
echo -e "   API Docs:     ${GREEN}http://localhost:$PORT/docs${NC}"
echo -e "   Flower:       ${GREEN}http://localhost:5555${NC}"
echo ""
echo -e "${BLUE}📁 Logs are in: logs/ directory${NC}"
echo -e "${BLUE}📄 PIDs are in: pids/ directory${NC}"
echo ""
echo -e "${YELLOW}To stop all services, run: ./stop.sh${NC}" 