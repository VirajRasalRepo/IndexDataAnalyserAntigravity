#!/bin/bash
# ============================================================
# Index Data Analyser - System Setup Script for Linux/Ubuntu
# This script installs all dependencies and sets up the system
# Tested on: Ubuntu 20.04/22.04/24.04, Debian 11/12
# ============================================================

set -e  # Exit on error

echo "============================================================"
echo "Index Data Analyser - System Setup"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${YELLOW}→ $1${NC}"; }
print_header() { echo -e "${BLUE}$1${NC}"; }

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root"
    echo "Run as a normal user with sudo access."
    exit 1
fi

# Get project directory (where this script lives)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    OS_ID=$ID
else
    print_error "Cannot detect OS. This script supports Ubuntu/Debian systems."
    exit 1
fi

print_info "Detected OS: $OS"
print_info "Project directory: $SCRIPT_DIR"
echo ""

# ============================================================
# 1. Update system packages and install essentials
# ============================================================
print_header "Step 1: System packages"
print_info "Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    curl \
    wget \
    git \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    logrotate \
    > /dev/null 2>&1
print_success "System packages installed"
echo ""

# ============================================================
# 2. Set timezone to IST (critical for market hours)
# ============================================================
print_header "Step 2: Timezone setup"
CURRENT_TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || echo "unknown")
if [ "$CURRENT_TZ" != "Asia/Kolkata" ]; then
    print_info "Setting timezone to Asia/Kolkata (IST)..."
    sudo timedatectl set-timezone Asia/Kolkata 2>/dev/null || \
        sudo ln -sf /usr/share/zoneinfo/Asia/Kolkata /etc/localtime
    print_success "Timezone set to IST (Asia/Kolkata)"
else
    print_success "Timezone already set to IST"
fi
echo ""

# ============================================================
# 3. Install MySQL Server
# ============================================================
print_header "Step 3: MySQL installation"
if ! command -v mysql &> /dev/null; then
    print_info "MySQL not found. Installing MySQL Server..."
    sudo apt-get install -y mysql-server mysql-client > /dev/null 2>&1
    sudo systemctl start mysql
    sudo systemctl enable mysql
    print_success "MySQL Server installed and started"
else
    MYSQL_VER=$(mysql --version 2>/dev/null | head -1)
    print_success "MySQL is already installed: $MYSQL_VER"
    # Ensure it's running
    if ! systemctl is-active --quiet mysql; then
        sudo systemctl start mysql
        print_info "Started MySQL service"
    fi
fi
echo ""

# ============================================================
# 4. Create Python virtual environment
# ============================================================
print_header "Step 4: Python virtual environment"
PYTHON_VERSION=$(python3 --version 2>&1)
print_info "Python version: $PYTHON_VERSION"

if [ ! -d "venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
print_success "Virtual environment activated"
echo ""

# ============================================================
# 5. Install Python dependencies
# ============================================================
print_header "Step 5: Python dependencies"
print_info "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

print_info "Installing project dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
print_success "All Python dependencies installed"

# Verify critical imports
print_info "Verifying critical imports..."
MISSING_PKGS=""
python3 -c "import flask" 2>/dev/null || MISSING_PKGS="$MISSING_PKGS flask"
python3 -c "import flask_cors" 2>/dev/null || MISSING_PKGS="$MISSING_PKGS flask-cors"
python3 -c "import mysql.connector" 2>/dev/null || MISSING_PKGS="$MISSING_PKGS mysql-connector-python"
python3 -c "import dotenv" 2>/dev/null || MISSING_PKGS="$MISSING_PKGS python-dotenv"
python3 -c "import websocket" 2>/dev/null || MISSING_PKGS="$MISSING_PKGS websocket-client"
python3 -c "import dhanhq" 2>/dev/null || MISSING_PKGS="$MISSING_PKGS dhanhq"
python3 -c "import gunicorn" 2>/dev/null || MISSING_PKGS="$MISSING_PKGS gunicorn"

if [ -z "$MISSING_PKGS" ]; then
    print_success "All critical packages verified"
else
    print_error "Missing packages:$MISSING_PKGS"
    print_info "Attempting to install missing packages..."
    pip install $MISSING_PKGS
fi
echo ""

# ============================================================
# 6. Setup environment variables
# ============================================================
print_header "Step 6: Environment configuration"
if [ ! -f ".env" ]; then
    cp .env.example .env
    print_success "Created .env file from template"
    echo ""
    print_error "IMPORTANT: Edit .env file with your configuration:"
    echo "  - DHAN_CLIENT_ID       (from https://dhanhq.co/developer)"
    echo "  - DHAN_ACCESS_TOKEN    (from Dhan API portal)"
    echo "  - DB_PASSWORD          (MySQL password you'll set below)"
    echo ""
    read -p "Press Enter to edit .env file now (or Ctrl+C to edit later)..." < /dev/tty
    ${EDITOR:-nano} .env
else
    print_info ".env file already exists"
fi

# Source .env for subsequent steps
set -a
source .env
set +a
echo ""

# ============================================================
# 7. Setup MySQL database and dedicated user
# ============================================================
print_header "Step 7: MySQL database setup"
echo ""
echo "Please enter MySQL root password when prompted."
echo "(If you just installed MySQL, the password might be empty — just press Enter)"
echo ""

read -sp "MySQL root password: " MYSQL_ROOT_PASSWORD < /dev/tty
echo ""

# Test MySQL connection
if mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1;" &> /dev/null; then
    print_success "MySQL root connection successful"

    # Create database
    print_info "Creating database and tables..."
    mysql -u root -p"$MYSQL_ROOT_PASSWORD" < setup_database.sql 2>/dev/null
    print_success "Primary database setup completed"

    # Run Greeks schema — use safe ALTER approach
    print_info "Applying Greeks analytics schema..."
    # Use --force to continue past duplicate column errors
    mysql -u root -p"$MYSQL_ROOT_PASSWORD" --force < setup_greeks_schema.sql 2>/dev/null || true
    print_success "Greeks schema applied"

    # Create dedicated DB user (not root) for the application
    DB_APP_USER="${DB_USER:-analyzer_user}"
    DB_APP_PASS="${DB_PASSWORD:-}"
    DB_APP_NAME="${DB_NAME:-analyzer_db}"

    if [ "$DB_APP_USER" != "root" ] && [ -n "$DB_APP_PASS" ]; then
        print_info "Creating dedicated database user: $DB_APP_USER"
        mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "
            CREATE USER IF NOT EXISTS '${DB_APP_USER}'@'localhost' IDENTIFIED BY '${DB_APP_PASS}';
            GRANT ALL PRIVILEGES ON ${DB_APP_NAME}.* TO '${DB_APP_USER}'@'localhost';
            FLUSH PRIVILEGES;
        " 2>/dev/null
        print_success "Database user '$DB_APP_USER' created with privileges on '$DB_APP_NAME'"
    else
        print_info "Using root user for database (configure DB_USER in .env for dedicated user)"
    fi
else
    print_error "Failed to connect to MySQL. Please check your password."
    echo ""
    echo "You can manually setup the database later:"
    echo "  mysql -u root -p < setup_database.sql"
    echo "  mysql -u root -p --force < setup_greeks_schema.sql"
fi
echo ""

# ============================================================
# 8. Create required directories
# ============================================================
print_header "Step 8: Directory structure"
mkdir -p logs
mkdir -p static
print_success "Created: logs/, static/"
echo ""

# ============================================================
# 9. Setup log rotation
# ============================================================
print_header "Step 9: Log rotation"
sudo tee /etc/logrotate.d/index-data-analyser > /dev/null <<EOF
${SCRIPT_DIR}/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    copytruncate
    su $(whoami) $(id -gn)
}
EOF
print_success "Log rotation configured (14 days, daily rotation)"
echo ""

# ============================================================
# 10. Setup UFW firewall rules (optional)
# ============================================================
print_header "Step 10: Firewall configuration"
if command -v ufw &> /dev/null; then
    read -p "Configure UFW firewall? (y/n) " -n 1 -r < /dev/tty
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo ufw allow 22/tcp    # SSH
        sudo ufw allow 5000/tcp  # Flask API
        sudo ufw allow 80/tcp    # HTTP (nginx)
        sudo ufw allow 443/tcp   # HTTPS (nginx)
        sudo ufw --force enable
        print_success "Firewall configured: SSH(22), API(5000), HTTP(80), HTTPS(443)"
    else
        print_info "Skipping firewall configuration"
    fi
else
    print_info "UFW not installed, skipping firewall setup"
fi
echo ""

# ============================================================
# 11. Setup nginx reverse proxy (optional)
# ============================================================
print_header "Step 11: Nginx reverse proxy (optional)"
read -p "Install and configure nginx as reverse proxy? (y/n) " -n 1 -r < /dev/tty
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if ! command -v nginx &> /dev/null; then
        sudo apt-get install -y nginx > /dev/null 2>&1
        print_success "Nginx installed"
    fi

    # Get server IP
    SERVER_IP=$(hostname -I | awk '{print $1}')

    sudo tee /etc/nginx/sites-available/index-data-analyser > /dev/null <<EOF
server {
    listen 80;
    server_name ${SERVER_IP} _;

    # Dashboard HTML files
    location / {
        root ${SCRIPT_DIR}/dashboard;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # API proxy to gunicorn
    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # Static files
    location /static/ {
        alias ${SCRIPT_DIR}/static/;
        expires 1d;
    }
}
EOF

    sudo ln -sf /etc/nginx/sites-available/index-data-analyser /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default

    # Test nginx config
    if sudo nginx -t &> /dev/null; then
        sudo systemctl restart nginx
        sudo systemctl enable nginx
        print_success "Nginx configured and running"
        echo "  Dashboard: http://${SERVER_IP}/"
        echo "  API: http://${SERVER_IP}/api/"
    else
        print_error "Nginx config test failed — check /etc/nginx/sites-available/index-data-analyser"
    fi
else
    print_info "Skipping nginx setup"
fi
echo ""

# ============================================================
# 12. Create systemd service files (optional)
# ============================================================
print_header "Step 12: Systemd services (optional)"
read -p "Create systemd services for auto-start on boot? (y/n) " -n 1 -r < /dev/tty
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Creating systemd service files..."

    # API service (gunicorn)
    sudo tee /etc/systemd/system/oi-dashboard-api.service > /dev/null <<EOF
[Unit]
Description=OI Dashboard API (Gunicorn)
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=$USER
Group=$(id -gn)
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$SCRIPT_DIR/venv/bin:/usr/local/bin:/usr/bin"
Environment="PYTHONPATH=$SCRIPT_DIR"
ExecStart=$SCRIPT_DIR/venv/bin/gunicorn \
    --workers 4 \
    --bind 0.0.0.0:5000 \
    --timeout 120 \
    --access-logfile $SCRIPT_DIR/logs/gunicorn-access.log \
    --error-logfile $SCRIPT_DIR/logs/gunicorn-error.log \
    dashboard.api:app
Restart=always
RestartSec=10
StandardOutput=append:$SCRIPT_DIR/logs/api.log
StandardError=append:$SCRIPT_DIR/logs/api-error.log

[Install]
WantedBy=multi-user.target
EOF

    # Data collector service
    sudo tee /etc/systemd/system/oi-data-collector.service > /dev/null <<EOF
[Unit]
Description=OI Data Collector (main.py)
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=$USER
Group=$(id -gn)
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$SCRIPT_DIR/venv/bin:/usr/local/bin:/usr/bin"
Environment="PYTHONPATH=$SCRIPT_DIR"
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=append:$SCRIPT_DIR/logs/data_collector.log
StandardError=append:$SCRIPT_DIR/logs/data_collector-error.log

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    print_success "Systemd services created"
    echo ""
    echo "  Enable and start:"
    echo "    sudo systemctl enable --now oi-dashboard-api"
    echo "    sudo systemctl enable --now oi-data-collector"
    echo ""
    echo "  Check status:"
    echo "    sudo systemctl status oi-dashboard-api"
    echo "    sudo systemctl status oi-data-collector"
    echo ""
fi

# ============================================================
# 13. Make all scripts executable
# ============================================================
print_header "Step 13: File permissions"
chmod +x start.sh stop.sh status.sh 2>/dev/null || true
print_success "Shell scripts are now executable"
echo ""

# ============================================================
# Setup Complete
# ============================================================
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo "============================================================"
print_success "Setup completed successfully!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Ensure .env file is configured with your credentials"
echo "  2. Run: ./start.sh to start all services"
echo ""
echo "Access (after starting):"
if command -v nginx &> /dev/null && systemctl is-active --quiet nginx 2>/dev/null; then
    echo "  Dashboard:  http://${SERVER_IP}/"
    echo "  Greeks:     http://${SERVER_IP}/greeks.html"
    echo "  API:        http://${SERVER_IP}/api/"
else
    echo "  API:        http://${SERVER_IP}:5000/api/"
    echo "  Dashboard:  http://${SERVER_IP}:5000/ (served by Flask)"
fi
echo ""
echo "Useful commands:"
echo "  ./start.sh          - Start all services"
echo "  ./stop.sh           - Stop all services"
echo "  ./status.sh         - Check service status"
echo "  tail -f logs/*.log  - Watch live logs"
echo ""
