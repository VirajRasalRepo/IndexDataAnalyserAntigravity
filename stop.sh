#!/bin/bash
# ============================================================
# Index Data Analyser - Stop All Services
# ============================================================

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_info() { echo -e "${YELLOW}→ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }

echo "============================================================"
echo "Stopping Index Data Analyser Services"
echo "============================================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

STOPPED_COUNT=0

# ============================================================
# Stop Data Collector
# ============================================================
if [ -f "logs/data_collector.pid" ]; then
    PID=$(cat logs/data_collector.pid)
    if ps -p $PID > /dev/null 2>&1; then
        print_info "Stopping Data Collector (PID: $PID)..."
        kill $PID
        sleep 2
        if ps -p $PID > /dev/null 2>&1; then
            print_info "Force killing Data Collector..."
            kill -9 $PID
        fi
        print_success "Data Collector stopped"
        STOPPED_COUNT=$((STOPPED_COUNT + 1))
    else
        print_info "Data Collector is not running"
    fi
    rm -f logs/data_collector.pid
else
    print_info "No Data Collector PID file found"
fi
echo ""

# ============================================================
# Stop Dashboard API
# ============================================================
if [ -f "logs/api.pid" ]; then
    PID=$(cat logs/api.pid)
    if ps -p $PID > /dev/null 2>&1; then
        print_info "Stopping Dashboard API (PID: $PID)..."
        kill $PID
        sleep 2
        if ps -p $PID > /dev/null 2>&1; then
            print_info "Force killing Dashboard API..."
            kill -9 $PID
        fi
        print_success "Dashboard API stopped"
        STOPPED_COUNT=$((STOPPED_COUNT + 1))
    else
        print_info "Dashboard API is not running"
    fi
    rm -f logs/api.pid
else
    print_info "No Dashboard API PID file found"
fi
echo ""

# ============================================================
# Cleanup any remaining Python processes
# ============================================================
print_info "Checking for any remaining Python processes..."
if pgrep -f "dashboard/api.py" > /dev/null; then
    print_info "Found remaining API processes, killing..."
    pkill -f "dashboard/api.py"
    STOPPED_COUNT=$((STOPPED_COUNT + 1))
fi

if pgrep -f "main.py" > /dev/null; then
    print_info "Found remaining Data Collector processes, killing..."
    pkill -f "main.py"
    STOPPED_COUNT=$((STOPPED_COUNT + 1))
fi
echo ""

# ============================================================
# Summary
# ============================================================
echo "============================================================"
if [ $STOPPED_COUNT -gt 0 ]; then
    print_success "All services stopped successfully"
else
    print_info "No services were running"
fi
echo "============================================================"
echo ""
