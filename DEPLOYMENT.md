# Index Data Analyser - Linux Deployment Guide

Complete guide for deploying the Index Data Analyser on a Linux server (Ubuntu/Debian).

## 📋 Prerequisites

- Ubuntu 20.04 or later (or Debian-based system)
- Root or sudo access
- Minimum 2GB RAM
- 10GB free disk space
- Internet connection
- Dhan API credentials ([Get from Dhan](https://dhanhq.co/developer))

## 🚀 Quick Start

### 1. Clone/Upload the Project

```bash
# If cloning from git
git clone <repository_url>
cd IndexDataAnalyser

# Or upload the project folder to your server
scp -r IndexDataAnalyser user@server:~/
```

### 2. Run Setup Script

```bash
chmod +x setup.sh
./setup.sh
```

This script will:
- Install MySQL Server
- Install Python 3 and dependencies
- Create virtual environment
- Setup database and tables
- Configure environment variables
- Create systemd services (optional)

### 3. Configure Environment

Edit the `.env` file with your credentials:

```bash
nano .env
```

Required configuration:
- `DHAN_CLIENT_ID` - Your Dhan API client ID
- `DHAN_ACCESS_TOKEN` - Your Dhan API access token
- `DB_PASSWORD` - MySQL root password

### 4. Start Services

```bash
./start.sh
```

### 5. Access Dashboard

Open in your browser:
```
file:///path/to/IndexDataAnalyser/dashboard/index.html
```

Or set up a web server (see Advanced Setup below).

## 📁 Project Structure

```
IndexDataAnalyser/
├── setup.sh              # One-time setup script
├── start.sh              # Start all services
├── stop.sh               # Stop all services
├── status.sh             # Check service status
├── setup_database.sql    # Database schema
├── .env.example          # Environment template
├── .env                  # Your configuration
├── requirements.txt      # Python dependencies
├── main.py               # Data collector service
├── dashboard/
│   ├── api.py           # Dashboard API server
│   ├── index.html       # Main dashboard
│   ├── option_chain.html
│   └── historical_data.html
├── core/
│   ├── config.py        # Configuration
│   └── database.py      # Database manager
└── logs/
    ├── api.log          # API logs
    └── data_collector.log
```

## 🛠️ Manual Setup (if setup.sh fails)

### 1. Install MySQL

```bash
sudo apt-get update
sudo apt-get install -y mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql
```

### 2. Create Database

```bash
mysql -u root -p < setup_database.sql
```

### 3. Install Python Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
nano .env
```

## 🔧 Service Management

### Using Shell Scripts

```bash
# Start services
./start.sh

# Stop services
./stop.sh

# Check status
./status.sh

# View logs
tail -f logs/api.log
tail -f logs/data_collector.log
```

### Using Systemd (if installed during setup)

```bash
# Enable auto-start on boot
sudo systemctl enable oi-dashboard-api
sudo systemctl enable oi-data-collector

# Start services
sudo systemctl start oi-dashboard-api
sudo systemctl start oi-data-collector

# Check status
sudo systemctl status oi-dashboard-api
sudo systemctl status oi-data-collector

# View logs
sudo journalctl -u oi-dashboard-api -f
sudo journalctl -u oi-data-collector -f

# Stop services
sudo systemctl stop oi-dashboard-api
sudo systemctl stop oi-data-collector
```

## 🌐 Advanced Setup - Web Server (Optional)

### Using Nginx to Serve Dashboard

1. Install Nginx:

```bash
sudo apt-get install nginx
```

2. Create Nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/oi-dashboard
```

Add configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Dashboard files
    location / {
        root /path/to/IndexDataAnalyser/dashboard;
        index index.html;
        try_files $uri $uri/ =404;
    }

    # API proxy
    location /api {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

3. Enable site and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/oi-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Now access at: `http://your-server-ip`

## 📊 Database Management

### Backup Database

```bash
mysqldump -u root -p analyzer_db > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
mysql -u root -p analyzer_db < backup_20260301.sql
```

### Check Database Status

```bash
mysql -u root -p
```

```sql
USE analyzer_db;
SHOW TABLES;
SELECT COUNT(*) FROM nifty_oc_historical;
SELECT * FROM nifty_oc_historical ORDER BY Date DESC, Time DESC LIMIT 10;
```

## 🐛 Troubleshooting

### Services Won't Start

1. Check logs:
```bash
cat logs/api.log
cat logs/data_collector.log
```

2. Check MySQL connection:
```bash
mysql -u root -p analyzer_db
```

3. Verify environment:
```bash
cat .env
source venv/bin/activate
python3 -c "import mysql.connector; print('OK')"
```

### Database Connection Errors

- Check MySQL is running: `sudo systemctl status mysql`
- Verify credentials in `.env`
- Check firewall: `sudo ufw status`

### API Not Accessible

- Check if port 5000 is listening: `netstat -tlnp | grep 5000`
- Check firewall: `sudo ufw allow 5000`
- Verify API is running: `curl http://localhost:5000/api/health`

### Python Package Errors

```bash
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

## 📈 Performance Optimization

### MySQL Optimization

Edit `/etc/mysql/mysql.conf.d/mysqld.cnf`:

```ini
[mysqld]
innodb_buffer_pool_size = 1G
max_connections = 200
query_cache_size = 64M
query_cache_limit = 2M
```

Restart MySQL:
```bash
sudo systemctl restart mysql
```

### Python Process Management with Gunicorn (Optional)

Install Gunicorn:
```bash
pip install gunicorn
```

Run API with Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 dashboard.api:app
```

## 🔒 Security Best Practices

1. **Change MySQL Root Password**:
```bash
sudo mysql_secure_installation
```

2. **Use Firewall**:
```bash
sudo ufw enable
sudo ufw allow 22   # SSH
sudo ufw allow 80   # HTTP (if using Nginx)
sudo ufw allow 5000 # API (only if exposing directly)
```

3. **Secure .env File**:
```bash
chmod 600 .env
```

4. **Regular Updates**:
```bash
sudo apt-get update && sudo apt-get upgrade
pip install --upgrade -r requirements.txt
```

## 📞 Support

- Check logs in `logs/` directory
- Run `./status.sh` for service status
- Verify `.env` configuration
- Check database connectivity

## ✅ Post-Installation Checklist

- [ ] MySQL is running and accessible
- [ ] Database `analyzer_db` created successfully
- [ ] Python virtual environment activated
- [ ] All dependencies installed
- [ ] `.env` file configured with valid credentials
- [ ] Data collector service running
- [ ] Dashboard API running on port 5000
- [ ] Dashboard accessible via browser
- [ ] Historical data loading correctly
- [ ] Weekend validation working
- [ ] Market hours (9:15 AM - 3:30 PM IST) configured

## 📝 Notes

- Market hours: 9:15 AM - 3:30 PM IST (Monday-Friday)
- API runs on port 5000 by default
- Data is stored in MySQL database `analyzer_db`
- Logs are stored in `logs/` directory
- PID files are in `logs/*.pid`

---

**Version**: 1.0
**Last Updated**: March 2026
**Market Timing**: Indian Stock Market (NSE)
