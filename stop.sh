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
# Stop Systemd Services (if they exist)
# ============================================================
if systemctl is-active --quiet oi-data-collector.service 2>/dev/null; then
    print_info "Stopping oi-data-collector systemd service..."
    sudo systemctl stop oi-data-collector.service
    print_success "oi-data-collector systemd service stopped"
    STOPPED_COUNT=$((STOPPED_COUNT + 1))
fi

if systemctl is-active --quiet oi-dashboard-api.service 2>/dev/null; then
    print_info "Stopping oi-dashboard-api systemd service..."
    sudo systemctl stop oi-dashboard-api.service
    print_success "oi-dashboard-api systemd service stopped"
    STOPPED_COUNT=$((STOPPED_COUNT + 1))
fi

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
            kill -9 $PID 2>/dev/null || true
        fi
        print_success "Data Collector stopped"
        STOPPED_COUNT=$((STOPPED_COUNT + 1))
    else
        print_info "Data Collector is not running (stale PID)"
    fi
    rm -f logs/data_collector.pid
else
    print_info "No Data Collector PID file found"
fi
echo ""

# ============================================================
# Stop Dashboard API (gunicorn master + workers)
# ============================================================
if [ -f "logs/api.pid" ]; then
    PID=$(cat logs/api.pid)
    if ps -p $PID > /dev/null 2>&1; then
        print_info "Stopping Dashboard API (PID: $PID)..."
        kill $PID
        sleep 2
        if ps -p $PID > /dev/null 2>&1; then
            print_info "Force killing Dashboard API..."
            kill -9 $PID 2>/dev/null || true
        fi
        print_success "Dashboard API stopped"
        STOPPED_COUNT=$((STOPPED_COUNT + 1))
    else
        print_info "Dashboard API is not running (stale PID)"
    fi
    rm -f logs/api.pid
else
    print_info "No Dashboard API PID file found"
fi
echo ""

# ============================================================
# Cleanup any remaining Python/gunicorn processes
# ============================================================
print_info "Checking for remaining processes..."

if pgrep -f "gunicorn.*dashboard.api" > /dev/null 2>&1; then
    print_info "Killing remaining gunicorn workers..."
    pkill -f "gunicorn.*dashboard.api" 2>/dev/null || true
    STOPPED_COUNT=$((STOPPED_COUNT + 1))
fi

if pgrep -f "python.*dashboard/api.py" > /dev/null 2>&1; then
    print_info "Killing remaining API processes..."
    pkill -f "python.*dashboard/api.py" 2>/dev/null || true
    STOPPED_COUNT=$((STOPPED_COUNT + 1))
fi

if pgrep -f "python.*main.py" > /dev/null 2>&1; then
    print_info "Killing remaining Data Collector processes..."
    pkill -f "python.*main.py" 2>/dev/null || true
    STOPPED_COUNT=$((STOPPED_COUNT + 1))
fi
echo ""

# ============================================================
# Summary
# ============================================================
echo "============================================================"
if [ $STOPPED_COUNT -gt 0 ]; then
    print_success "All services stopped ($STOPPED_COUNT processes terminated)"
else
    print_info "No services were running"
fi
echo "============================================================"
echo ""
