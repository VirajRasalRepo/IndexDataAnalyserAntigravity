#!/bin/bash
# ============================================================
# Index Data Analyser - Check Service Status
# ============================================================

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_info() { echo -e "${YELLOW}→ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_header() { echo -e "${BLUE}$1${NC}"; }

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "Index Data Analyser - Service Status"
echo "============================================================"
echo ""

RUNNING_COUNT=0
TOTAL_COUNT=2

# ============================================================
# Check Data Collector
# ============================================================
print_header "Data Collector (main.py)"
if [ -f "logs/data_collector.pid" ]; then
    PID=$(cat logs/data_collector.pid)
    if ps -p $PID > /dev/null 2>&1; then
        print_success "RUNNING (PID: $PID)"
        echo "  CPU: $(ps -p $PID -o %cpu= | xargs)%"
        echo "  MEM: $(ps -p $PID -o %mem= | xargs)%"
        echo "  Started: $(ps -p $PID -o lstart= | xargs)"
        RUNNING_COUNT=$((RUNNING_COUNT + 1))
    else
        print_error "NOT RUNNING (stale PID file)"
    fi
else
    print_error "NOT RUNNING (no PID file)"
fi
echo ""

# ============================================================
# Check Dashboard API
# ============================================================
print_header "Dashboard API (api.py)"
if [ -f "logs/api.pid" ]; then
    PID=$(cat logs/api.pid)
    if ps -p $PID > /dev/null 2>&1; then
        print_success "RUNNING (PID: $PID)"
        echo "  CPU: $(ps -p $PID -o %cpu= | xargs)%"
        echo "  MEM: $(ps -p $PID -o %mem= | xargs)%"
        echo "  Started: $(ps -p $PID -o lstart= | xargs)"
        echo "  Endpoint: http://localhost:5000/api"

        # Check if API is responding
        if command -v curl &> /dev/null; then
            if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
                print_success "API health check: OK"
            else
                print_error "API health check: FAILED"
            fi
        fi
        RUNNING_COUNT=$((RUNNING_COUNT + 1))
    else
        print_error "NOT RUNNING (stale PID file)"
    fi
else
    print_error "NOT RUNNING (no PID file)"
fi
echo ""

# ============================================================
# Check MySQL Connection
# ============================================================
print_header "MySQL Database"
if [ -f ".env" ]; then
    source .env
    if python3 -c "import mysql.connector; mysql.connector.connect(host='$DB_HOST', user='$DB_USER', password='$DB_PASSWORD', database='$DB_NAME')" 2>/dev/null; then
        print_success "Connected to database: $DB_NAME"
    else
        print_error "Cannot connect to database"
    fi
else
    print_error ".env file not found"
fi
echo ""

# ============================================================
# Log Files
# ============================================================
print_header "Recent Log Entries"
if [ -f "logs/api.log" ]; then
    echo "API Log (last 3 lines):"
    tail -n 3 logs/api.log | sed 's/^/  /'
fi
echo ""
if [ -f "logs/data_collector.log" ]; then
    echo "Data Collector Log (last 3 lines):"
    tail -n 3 logs/data_collector.log | sed 's/^/  /'
fi
echo ""

# ============================================================
# Summary
# ============================================================
echo "============================================================"
echo "Summary: $RUNNING_COUNT/$TOTAL_COUNT services running"
echo "============================================================"
echo ""

if [ $RUNNING_COUNT -eq $TOTAL_COUNT ]; then
    print_success "All services are running!"
    echo ""
    echo "Access Information:"
    echo "  Dashboard: file://$SCRIPT_DIR/dashboard/index.html"
    echo "  API: http://localhost:5000/api"
elif [ $RUNNING_COUNT -eq 0 ]; then
    print_error "No services are running"
    echo "Run: ./start.sh to start services"
else
    print_info "Some services are not running"
    echo "Run: ./start.sh to start all services"
fi
echo ""

# ============================================================
# Quick Actions
# ============================================================
echo "Quick Actions:"
echo "  ./start.sh          - Start all services"
echo "  ./stop.sh           - Stop all services"
echo "  tail -f logs/*.log  - Watch live logs"
echo ""
