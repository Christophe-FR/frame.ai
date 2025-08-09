#!/bin/bash

echo "🛑 Stopping Frame Interpolation Project"
echo "======================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create directories for logs and PIDs if they don't exist
mkdir -p logs pids

# Function to stop a service by PID file
stop_service() {
    local service_name=$1
    local pid_file="pids/${service_name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${BLUE}🛑 Stopping ${service_name} (PID: $pid)...${NC}"
            kill -TERM $pid
            
            # Wait for graceful shutdown
            local count=0
            while ps -p $pid > /dev/null 2>&1 && [ $count -lt 10 ]; do
                sleep 1
                ((count++))
            done
            
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo -e "${YELLOW}⚠️  Force killing ${service_name}...${NC}"
                kill -9 $pid
            fi
            
            echo -e "${GREEN}✅ ${service_name} stopped${NC}"
        else
            echo -e "${YELLOW}⚠️  ${service_name} was not running${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${YELLOW}⚠️  No PID file found for ${service_name}${NC}"
    fi
}

# Function to stop processes by pattern
stop_by_pattern() {
    local pattern=$1
    local service_name=$2
    
    echo -e "${BLUE}🔍 Looking for ${service_name} processes...${NC}"
    local pids=$(pgrep -f "$pattern")
    
    if [ -n "$pids" ]; then
        echo -e "${BLUE}🛑 Stopping ${service_name} processes: $pids${NC}"
        pkill -TERM -f "$pattern"
        sleep 3
        
        # Force kill any remaining processes
        local remaining=$(pgrep -f "$pattern")
        if [ -n "$remaining" ]; then
            echo -e "${YELLOW}⚠️  Force killing remaining ${service_name} processes...${NC}"
            pkill -9 -f "$pattern"
        fi
        echo -e "${GREEN}✅ ${service_name} stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  No ${service_name} processes found${NC}"
    fi
}

# Stop services in reverse order (frontend first, backend last)
echo -e "${BLUE}🔄 Stopping services...${NC}"

# Stop React Frontend
stop_service "react"
stop_by_pattern "npm start" "React/npm"
stop_by_pattern "react-scripts" "React scripts"

# Stop Celery Worker
stop_service "celery"
stop_by_pattern "celery.*worker" "Celery worker"

# Stop Flower
stop_service "flower"
stop_by_pattern "flower.*broker" "Flower"

# Stop FastAPI Backend
stop_service "fastapi"
stop_by_pattern "server_fastapi" "FastAPI"
stop_by_pattern "uvicorn" "Uvicorn"

# Additional cleanup for any Python servers
stop_by_pattern "python.*server" "Python servers"

echo ""
echo -e "${BLUE}🧹 Cleaning up...${NC}"

# Clean up any remaining processes on project ports
for port in 3500 8500 8501 5555; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Killing process on port $port...${NC}"
        lsof -ti :$port | xargs kill -9 2>/dev/null || true
    fi
done

# Clean up PID files
rm -f pids/*.pid

echo ""
echo -e "${GREEN}✅ All services stopped successfully!${NC}"
echo ""
echo -e "${BLUE}📁 Logs preserved in: logs/ directory${NC}"
echo -e "${YELLOW}To start all services, run: ./start.sh${NC}" 