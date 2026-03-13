#!/bin/bash
# ============================================================
# Index Data Analyser - Start All Services
# ============================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_info() { echo -e "${YELLOW}→ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }

echo "============================================================"
echo "Starting Index Data Analyser Services"
echo "============================================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Export PYTHONPATH so all Python processes can find core/ modules
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# ============================================================
# Pre-flight checks
# ============================================================
print_info "Running pre-flight checks..."

# Check .env file
# ============================================================
# Cleanup: Stop old processes and free ports
# ============================================================
print_info "Cleaning up old processes..."

# Stop systemd services if running (to avoid duplicate instances)
if systemctl is-active --quiet ida-collector.service 2>/dev/null; then
    print_info "Stopping ida-collector systemd service..."
    sudo systemctl stop ida-collector.service
    print_success "ida-collector systemd service stopped"
fi

if systemctl is-active --quiet ida-api.service 2>/dev/null; then
    print_info "Stopping ida-api systemd service..."
    sudo systemctl stop ida-api.service
    print_success "ida-api systemd service stopped"
fi

# Kill old collector process if running
if [ -f "logs/data_collector.pid" ]; then
    OLD_PID=$(cat logs/data_collector.pid)
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        print_info "Killing old Data Collector (PID: $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
        # Force kill if still alive
        kill -9 "$OLD_PID" 2>/dev/null || true
    fi
    rm -f logs/data_collector.pid
fi

# Kill old API process if running
if [ -f "logs/api.pid" ]; then
    OLD_PID=$(cat logs/api.pid)
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        print_info "Killing old Dashboard API (PID: $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
        kill -9 "$OLD_PID" 2>/dev/null || true
    fi
    rm -f logs/api.pid
fi

# Kill any remaining main.py processes (catch strays)
pkill -f "python3 main.py" 2>/dev/null || true
pkill -f "python3 dashboard/api.py" 2>/dev/null || true

# Free port 5000 if still in use
if fuser 5000/tcp > /dev/null 2>&1; then
    print_info "Freeing port 5000..."
    fuser -k 5000/tcp > /dev/null 2>&1 || true
    sleep 1
fi

print_success "Cleanup complete"
echo ""

# ============================================================
# Check if .env file exists
# ============================================================
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    echo "Please run setup.sh first or create .env from .env.example"
    exit 1
fi
print_success ".env file found"

# Source .env for MySQL check
set -a
source .env
set +a

# Check virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    print_success "Virtual environment activated"
else
    print_error "Virtual environment not found! Run setup.sh first."
    exit 1
fi

# Check MySQL connection
print_info "Checking MySQL connection..."
if python3 -c "
import mysql.connector
mysql.connector.connect(
    host='${DB_HOST:-localhost}',
    user='${DB_USER:-root}',
    password='${DB_PASSWORD}',
    database='${DB_NAME:-analyzer_db}',
    port=${DB_PORT:-3306}
)
print('ok')
" 2>/dev/null | grep -q "ok"; then
    print_success "MySQL connection successful (${DB_NAME:-analyzer_db}@${DB_HOST:-localhost})"
else
    print_error "Cannot connect to MySQL database"
    echo "  Host: ${DB_HOST:-localhost}:${DB_PORT:-3306}"
    echo "  User: ${DB_USER:-root}"
    echo "  Database: ${DB_NAME:-analyzer_db}"
    echo "  Please check your .env configuration"
    exit 1
fi

# Check critical Python imports
print_info "Verifying Python imports..."
if python3 -c "from core.config import Config; from dashboard.api import app; print('ok')" 2>/dev/null | grep -q "ok"; then
    print_success "Python imports verified"
else
    print_error "Python import check failed. Check PYTHONPATH and dependencies."
    echo "  PYTHONPATH=$PYTHONPATH"
    echo "  Try: pip install -r requirements.txt"
    exit 1
fi

echo ""

# ============================================================
# Create directories
# ============================================================
mkdir -p logs
print_info "Log directory: $SCRIPT_DIR/logs"
echo ""

# ============================================================
# Stop existing services (if running)
# ============================================================
print_info "Checking for existing processes..."
if [ -f "logs/data_collector.pid" ]; then
    OLD_PID=$(cat logs/data_collector.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        print_info "Stopping existing Data Collector (PID: $OLD_PID)..."
        kill $OLD_PID 2>/dev/null || true
        sleep 2
        kill -9 $OLD_PID 2>/dev/null || true
    fi
    rm -f logs/data_collector.pid
fi

if [ -f "logs/api.pid" ]; then
    OLD_PID=$(cat logs/api.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        print_info "Stopping existing Dashboard API (PID: $OLD_PID)..."
        kill $OLD_PID 2>/dev/null || true
        sleep 2
        kill -9 $OLD_PID 2>/dev/null || true
    fi
    rm -f logs/api.pid
fi

# Also kill any orphan gunicorn workers
pkill -f "gunicorn.*dashboard.api" 2>/dev/null || true
echo ""

# ============================================================
# Start Data Collector (main.py)
# ============================================================
print_info "Starting Data Collector (main.py)..."
if [ -f "main.py" ]; then
    nohup python3 "$SCRIPT_DIR/main.py" \
        >> logs/data_collector.log 2>&1 &
    COLLECTOR_PID=$!
    echo $COLLECTOR_PID > logs/data_collector.pid
    print_success "Data Collector started (PID: $COLLECTOR_PID)"
    echo "  Log: logs/data_collector.log"
else
    print_error "main.py not found!"
fi
echo ""

# ============================================================
# Start Dashboard API (gunicorn or flask dev server)
# ============================================================
print_info "Starting Dashboard API..."
if [ -f "dashboard/api.py" ]; then
    # Use gunicorn in production, flask dev server as fallback
    if command -v gunicorn &> /dev/null || [ -f "venv/bin/gunicorn" ]; then
        print_info "Using gunicorn (production mode)"
        nohup gunicorn \
            --workers 4 \
            --bind 0.0.0.0:5000 \
            --timeout 120 \
            --chdir "$SCRIPT_DIR" \
            --access-logfile logs/gunicorn-access.log \
            --error-logfile logs/gunicorn-error.log \
            dashboard.api:app \
            >> logs/api.log 2>&1 &
        API_PID=$!
    else
        print_info "gunicorn not found, using Flask dev server (not for production!)"
        # IMPORTANT: Run from project root with PYTHONPATH set, NOT from dashboard/
        nohup python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from dashboard.api import app
app.run(host='0.0.0.0', port=5000, debug=False)
" >> logs/api.log 2>&1 &
        API_PID=$!
    fi
    nohup python3 dashboard/api.py > logs/api.log 2>&1 &
    API_PID=$!
    echo $API_PID > logs/api.pid
    print_success "Dashboard API started (PID: $API_PID)"
    echo "  Endpoint: http://0.0.0.0:5000"
    echo "  Log: logs/api.log"
else
    print_error "dashboard/api.py not found!"
fi
echo ""

# ============================================================
# Wait for services and run health checks
# ============================================================
print_info "Waiting for services to initialize..."
sleep 4

COLLECTOR_RUNNING=false
API_RUNNING=false
API_HEALTHY=false

# Check Data Collector
if [ -f "logs/data_collector.pid" ]; then
    if ps -p $(cat logs/data_collector.pid) > /dev/null 2>&1; then
        COLLECTOR_RUNNING=true
    fi
fi

# Check API process
if [ -f "logs/api.pid" ]; then
    if ps -p $(cat logs/api.pid) > /dev/null 2>&1; then
        API_RUNNING=true
    fi
fi

# Health check: try API endpoint with retry
if [ "$API_RUNNING" = true ]; then
    print_info "Running API health check..."
    for i in 1 2 3 4 5; do
        if curl -sf http://localhost:5000/api/available-dates > /dev/null 2>&1; then
            API_HEALTHY=true
            break
        fi
        sleep 2
    done
fi

# ============================================================
# Status Summary
# ============================================================
echo ""
echo "============================================================"
echo "Service Status"
echo "============================================================"

if [ "$COLLECTOR_RUNNING" = true ]; then
    print_success "Data Collector: RUNNING (PID: $(cat logs/data_collector.pid))"
else
    print_error "Data Collector: FAILED"
    echo "  Check: tail -20 logs/data_collector.log"
fi

if [ "$API_RUNNING" = true ]; then
    if [ "$API_HEALTHY" = true ]; then
        print_success "Dashboard API:  RUNNING + HEALTHY (PID: $(cat logs/api.pid))"
    else
        print_info "Dashboard API:  RUNNING but health check pending (PID: $(cat logs/api.pid))"
    fi
else
    print_error "Dashboard API:  FAILED"
    echo "  Check: tail -20 logs/api.log"
fi

echo ""

# ============================================================
# Access Information
# ============================================================
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo "============================================================"
echo "Access Information"
echo "============================================================"
if command -v nginx &> /dev/null && systemctl is-active --quiet nginx 2>/dev/null; then
    echo "  Dashboard:      http://${SERVER_IP}/"
    echo "  Greeks:         http://${SERVER_IP}/greeks.html"
    echo "  Option Chain:   http://${SERVER_IP}/option_chain.html"
    echo "  Historical:     http://${SERVER_IP}/historical_data.html"
    echo "  API Endpoint:   http://${SERVER_IP}/api/"
else
    echo "  API Endpoint:   http://${SERVER_IP}:5000/api/"
    echo "  Dashboard:      http://${SERVER_IP}:5000/"
fi
echo ""
echo "Commands:"
echo "  ./stop.sh           - Stop all services"
echo "  ./status.sh         - Check service status"
echo "  tail -f logs/*.log  - Watch live logs"
echo ""
