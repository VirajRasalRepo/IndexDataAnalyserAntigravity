#!/bin/bash
# ============================================================
# Index Data Analyser - Start All Services
# ============================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    echo "Please run setup.sh first or create .env from .env.example"
    exit 1
fi

# ============================================================
# Activate virtual environment
# ============================================================
if [ -d "venv" ]; then
    print_info "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"
else
    print_error "Virtual environment not found!"
    echo "Please run setup.sh first"
    exit 1
fi
echo ""

# ============================================================
# Check MySQL connection
# ============================================================
print_info "Checking MySQL connection..."
source .env
if python3 -c "import mysql.connector; mysql.connector.connect(host='$DB_HOST', user='$DB_USER', password='$DB_PASSWORD', database='$DB_NAME')" 2>/dev/null; then
    print_success "MySQL connection successful"
else
    print_error "Cannot connect to MySQL database"
    echo "Please check your database configuration in .env"
    exit 1
fi
echo ""

# ============================================================
# Create log directory
# ============================================================
mkdir -p logs
print_info "Log directory: $SCRIPT_DIR/logs"
echo ""

# ============================================================
# Start Data Collector
# ============================================================
print_info "Starting Data Collector (main.py)..."
if [ -f "main.py" ]; then
    nohup python3 main.py > logs/data_collector.log 2>&1 &
    COLLECTOR_PID=$!
    echo $COLLECTOR_PID > logs/data_collector.pid
    print_success "Data Collector started (PID: $COLLECTOR_PID)"
    echo "  Log file: logs/data_collector.log"
else
    print_error "main.py not found!"
fi
echo ""

# ============================================================
# Start Dashboard API
# ============================================================
print_info "Starting Dashboard API..."
if [ -f "dashboard/api.py" ]; then
    cd dashboard
    nohup python3 api.py > ../logs/api.log 2>&1 &
    API_PID=$!
    echo $API_PID > ../logs/api.pid
    cd ..
    print_success "Dashboard API started (PID: $API_PID)"
    echo "  API endpoint: http://localhost:5000"
    echo "  Log file: logs/api.log"
else
    print_error "dashboard/api.py not found!"
fi
echo ""

# ============================================================
# Wait for services to start
# ============================================================
print_info "Waiting for services to initialize..."
sleep 3

# Check if processes are running
COLLECTOR_RUNNING=false
API_RUNNING=false

if [ -f "logs/data_collector.pid" ]; then
    if ps -p $(cat logs/data_collector.pid) > /dev/null 2>&1; then
        COLLECTOR_RUNNING=true
    fi
fi

if [ -f "logs/api.pid" ]; then
    if ps -p $(cat logs/api.pid) > /dev/null 2>&1; then
        API_RUNNING=true
    fi
fi

# ============================================================
# Status Summary
# ============================================================
echo "============================================================"
echo "Service Status"
echo "============================================================"

if [ "$COLLECTOR_RUNNING" = true ]; then
    print_success "Data Collector: RUNNING"
else
    print_error "Data Collector: FAILED"
    echo "  Check logs/data_collector.log for errors"
fi

if [ "$API_RUNNING" = true ]; then
    print_success "Dashboard API: RUNNING"
else
    print_error "Dashboard API: FAILED"
    echo "  Check logs/api.log for errors"
fi

echo ""
echo "============================================================"
echo "Access Information"
echo "============================================================"
echo "Dashboard: file://$SCRIPT_DIR/dashboard/index.html"
echo "Option Chain: file://$SCRIPT_DIR/dashboard/option_chain.html"
echo "Historical Data: file://$SCRIPT_DIR/dashboard/historical_data.html"
echo "API Endpoint: http://localhost:5000/api"
echo ""
echo "To stop services: ./stop.sh"
echo "To check status: ./status.sh"
echo "To view logs: tail -f logs/*.log"
echo ""
