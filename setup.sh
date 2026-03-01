#!/bin/bash
# ============================================================
# Index Data Analyser - System Setup Script for Linux/Ubuntu
# This script installs all dependencies and sets up the system
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
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root"
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
else
    print_error "Cannot detect OS. This script supports Ubuntu/Debian systems."
    exit 1
fi

print_info "Detected OS: $OS"
echo ""

# ============================================================
# 1. Update system packages
# ============================================================
print_info "Updating system packages..."
sudo apt-get update
print_success "System packages updated"
echo ""

# ============================================================
# 2. Install MySQL Server
# ============================================================
print_info "Checking MySQL installation..."
if ! command -v mysql &> /dev/null; then
    print_info "MySQL not found. Installing MySQL Server..."
    sudo apt-get install -y mysql-server
    sudo systemctl start mysql
    sudo systemctl enable mysql
    print_success "MySQL Server installed and started"
else
    print_success "MySQL is already installed"
fi
echo ""

# ============================================================
# 3. Install Python 3 and pip
# ============================================================
print_info "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_info "Python3 not found. Installing..."
    sudo apt-get install -y python3 python3-pip python3-venv
    print_success "Python3 installed"
else
    PYTHON_VERSION=$(python3 --version)
    print_success "Python is already installed: $PYTHON_VERSION"
fi
echo ""

# ============================================================
# 4. Create Python virtual environment
# ============================================================
print_info "Creating Python virtual environment..."
if [ ! -d "venv" ]; then
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
print_info "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
print_success "Python dependencies installed"
echo ""

# ============================================================
# 6. Setup environment variables
# ============================================================
print_info "Setting up environment variables..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    print_success "Created .env file from template"
    echo ""
    print_error "IMPORTANT: Please edit .env file with your configuration:"
    echo "  - DHAN_CLIENT_ID"
    echo "  - DHAN_ACCESS_TOKEN"
    echo "  - DB_PASSWORD"
    echo ""
    read -p "Press Enter to edit .env file now (or Ctrl+C to exit and edit later)..."
    ${EDITOR:-nano} .env
else
    print_info ".env file already exists"
fi
echo ""

# ============================================================
# 7. Setup MySQL database
# ============================================================
print_info "Setting up MySQL database..."
echo ""
echo "Please enter MySQL root password when prompted."
echo "If you just installed MySQL, the password might be empty (just press Enter)."
echo ""

read -sp "MySQL root password: " MYSQL_ROOT_PASSWORD
echo ""

# Test MySQL connection
if mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1;" &> /dev/null; then
    print_success "MySQL connection successful"

    # Run database setup script
    print_info "Creating database and tables..."
    mysql -u root -p"$MYSQL_ROOT_PASSWORD" < setup_database.sql
    print_success "Database setup completed"
else
    print_error "Failed to connect to MySQL. Please check your password."
    echo ""
    echo "You can manually setup the database later by running:"
    echo "  mysql -u root -p < setup_database.sql"
fi
echo ""

# ============================================================
# 8. Create systemd service files (optional)
# ============================================================
read -p "Do you want to create systemd services for auto-start? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Creating systemd service files..."

    # Get current directory
    CURRENT_DIR=$(pwd)

    # Create API service
    sudo tee /etc/systemd/system/oi-dashboard-api.service > /dev/null <<EOF
[Unit]
Description=OI Dashboard API Service
After=network.target mysql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$CURRENT_DIR/venv/bin"
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/dashboard/api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Create data collector service
    sudo tee /etc/systemd/system/oi-data-collector.service > /dev/null <<EOF
[Unit]
Description=OI Data Collector Service
After=network.target mysql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$CURRENT_DIR/venv/bin"
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    sudo systemctl daemon-reload

    print_success "Systemd services created"
    echo ""
    echo "To enable and start services:"
    echo "  sudo systemctl enable oi-dashboard-api"
    echo "  sudo systemctl start oi-dashboard-api"
    echo "  sudo systemctl enable oi-data-collector"
    echo "  sudo systemctl start oi-data-collector"
    echo ""
fi

# ============================================================
# 9. Make scripts executable
# ============================================================
print_info "Making scripts executable..."
chmod +x start.sh stop.sh status.sh
print_success "Scripts are now executable"
echo ""

# ============================================================
# Setup Complete
# ============================================================
echo "============================================================"
print_success "Setup completed successfully!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Ensure .env file is configured with your credentials"
echo "  2. Run: ./start.sh to start all services"
echo "  3. Access dashboard at: file://$(pwd)/dashboard/index.html"
echo "  4. API will be available at: http://localhost:5000"
echo ""
echo "Useful commands:"
echo "  ./start.sh   - Start all services"
echo "  ./stop.sh    - Stop all services"
echo "  ./status.sh  - Check service status"
echo ""
