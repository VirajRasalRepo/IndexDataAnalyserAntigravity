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
TOTAL_COUNT=3  # Collector + API + MySQL

# ============================================================
# System Info
# ============================================================
print_header "System"
echo "  Timezone:  $(timedatectl show --property=Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || echo 'unknown')"
echo "  Time:      $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  Uptime:   $(uptime -p 2>/dev/null || uptime)"
echo ""

# ============================================================
# Check MySQL
# ============================================================
print_header "MySQL Database"
if systemctl is-active --quiet mysql 2>/dev/null; then
    print_success "MySQL service: RUNNING"
    RUNNING_COUNT=$((RUNNING_COUNT + 1))

    if [ -f ".env" ]; then
        set -a; source .env; set +a
        if python3 -c "
import mysql.connector
c = mysql.connector.connect(host='${DB_HOST:-localhost}', user='${DB_USER:-root}', password='${DB_PASSWORD}', database='${DB_NAME:-analyzer_db}', port=${DB_PORT:-3306})
cur = c.cursor()
cur.execute('SELECT COUNT(*) FROM nifty_oc_historical')
rows = cur.fetchone()[0]
cur.execute('SELECT MAX(Date), MAX(Time) FROM nifty_oc_historical')
latest = cur.fetchone()
print(f'rows={rows}|date={latest[0]}|time={latest[1]}')
c.close()
" 2>/dev/null > /tmp/db_status.txt; then
            DB_INFO=$(cat /tmp/db_status.txt)
            ROWS=$(echo "$DB_INFO" | grep -oP 'rows=\K[0-9]+')
            LATEST_DATE=$(echo "$DB_INFO" | grep -oP 'date=\K[^\|]+')
            LATEST_TIME=$(echo "$DB_INFO" | grep -oP 'time=\K.*')
            echo "  Database:  ${DB_NAME:-analyzer_db} ($ROWS rows)"
            echo "  Latest:    $LATEST_DATE $LATEST_TIME"
            rm -f /tmp/db_status.txt
        else
            print_error "Cannot query database (check .env credentials)"
        fi
    else
        print_error ".env file not found"
    fi
else
    print_error "MySQL service: NOT RUNNING"
    echo "  Start with: sudo systemctl start mysql"
fi
echo ""

# ============================================================
# Check Data Collector
# ============================================================
print_header "Data Collector (main.py)"
if [ -f "logs/data_collector.pid" ]; then
    PID=$(cat logs/data_collector.pid)
    if ps -p $PID > /dev/null 2>&1; then
        print_success "RUNNING (PID: $PID)"
        echo "  CPU: $(ps -p $PID -o %cpu= 2>/dev/null | xargs)%"
        echo "  MEM: $(ps -p $PID -o %mem= 2>/dev/null | xargs)%"
        echo "  Started: $(ps -p $PID -o lstart= 2>/dev/null | xargs)"
        RUNNING_COUNT=$((RUNNING_COUNT + 1))
    else
        print_error "NOT RUNNING (stale PID file)"
        echo "  Last log entries:"
        tail -3 logs/data_collector.log 2>/dev/null | sed 's/^/    /' || echo "    (no log file)"
    fi
else
    print_error "NOT RUNNING (no PID file)"
fi
echo ""

# ============================================================
# Check Dashboard API
# ============================================================
print_header "Dashboard API"
if [ -f "logs/api.pid" ]; then
    PID=$(cat logs/api.pid)
    if ps -p $PID > /dev/null 2>&1; then
        # Detect if gunicorn or flask
        PROC_NAME=$(ps -p $PID -o comm= 2>/dev/null)
        if echo "$PROC_NAME" | grep -q "gunicorn"; then
            WORKER_COUNT=$(pgrep -P $PID | wc -l)
            print_success "RUNNING via gunicorn (PID: $PID, Workers: $WORKER_COUNT)"
        else
            print_success "RUNNING via Flask dev server (PID: $PID)"
            print_info "Consider installing gunicorn for production"
        fi

        echo "  CPU: $(ps -p $PID -o %cpu= 2>/dev/null | xargs)%"
        echo "  MEM: $(ps -p $PID -o %mem= 2>/dev/null | xargs)%"
        echo "  Endpoint: http://localhost:5000/api"

        # API health check
        if command -v curl &> /dev/null; then
            HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:5000/api/available-dates 2>/dev/null || echo "000")
            if [ "$HTTP_CODE" = "200" ]; then
                print_success "API health check: OK (HTTP $HTTP_CODE)"
            else
                print_error "API health check: FAILED (HTTP $HTTP_CODE)"
            fi
        fi
        RUNNING_COUNT=$((RUNNING_COUNT + 1))
    else
        print_error "NOT RUNNING (stale PID file)"
        echo "  Last log entries:"
        tail -3 logs/api.log 2>/dev/null | sed 's/^/    /' || echo "    (no log file)"
    fi
else
    print_error "NOT RUNNING (no PID file)"
fi
echo ""

# ============================================================
# Check nginx (if installed)
# ============================================================
if command -v nginx &> /dev/null; then
    print_header "Nginx Reverse Proxy"
    if systemctl is-active --quiet nginx 2>/dev/null; then
        print_success "RUNNING"
        SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
        echo "  Dashboard: http://${SERVER_IP}/"
    else
        print_error "NOT RUNNING"
        echo "  Start with: sudo systemctl start nginx"
    fi
    echo ""
fi

# ============================================================
# Disk usage
# ============================================================
print_header "Disk Usage"
LOG_SIZE=$(du -sh logs/ 2>/dev/null | awk '{print $1}' || echo "0")
echo "  Log files: $LOG_SIZE"
echo ""

# ============================================================
# Log Files (recent entries)
# ============================================================
print_header "Recent Log Entries"
if [ -f "logs/api.log" ]; then
    echo "API Log (last 3 lines):"
    tail -n 3 logs/api.log 2>/dev/null | sed 's/^/  /'
fi
echo ""
if [ -f "logs/data_collector.log" ]; then
    echo "Data Collector Log (last 3 lines):"
    tail -n 3 logs/data_collector.log 2>/dev/null | sed 's/^/  /'
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
elif [ $RUNNING_COUNT -eq 0 ]; then
    print_error "No services are running"
    echo "  Run: ./start.sh to start services"
else
    print_info "Some services are not running"
    echo "  Run: ./start.sh to start all services"
fi
echo ""

echo "Quick Actions:"
echo "  ./start.sh          - Start all services"
echo "  ./stop.sh           - Stop all services"
echo "  tail -f logs/*.log  - Watch live logs"
echo ""
