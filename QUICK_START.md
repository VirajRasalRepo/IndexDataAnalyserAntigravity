# Quick Start Guide - Linux Deployment

## 🚀 One-Command Setup

```bash
chmod +x setup.sh && ./setup.sh
```

This single command will set up everything automatically!

## 📦 What Gets Installed

1. **MySQL Server** - Database for storing market data
2. **Python 3 + pip** - Runtime environment
3. **Virtual Environment** - Isolated Python environment
4. **All Dependencies** - From requirements.txt
5. **Database Schema** - Tables for option chain data
6. **Systemd Services** - Optional auto-start services

## ⚡ Basic Commands

### Setup (Run Once)
```bash
./setup.sh
```

### Start Services
```bash
./start.sh
```

### Stop Services
```bash
./stop.sh
```

### Check Status
```bash
./status.sh
```

### View Logs
```bash
tail -f logs/api.log
tail -f logs/data_collector.log
```

## 📁 Files Created

| File | Purpose |
|------|---------|
| `setup_database.sql` | Database schema |
| `setup.sh` | One-time system setup |
| `start.sh` | Start all services |
| `stop.sh` | Stop all services |
| `status.sh` | Check service status |
| `.env.example` | Configuration template |
| `DEPLOYMENT.md` | Full documentation |

## ⚙️ Configuration

Edit `.env` file with your credentials:

```bash
nano .env
```

Required settings:
- `DHAN_CLIENT_ID` - Get from https://dhanhq.co/developer
- `DHAN_ACCESS_TOKEN` - Your API access token
- `DB_PASSWORD` - MySQL database password

## 🌐 Access URLs

After starting services:

- **Main Dashboard**: `file:///path/to/IndexDataAnalyser/dashboard/index.html`
- **Option Chain**: `file:///path/to/IndexDataAnalyser/dashboard/option_chain.html`
- **Historical Data**: `file:///path/to/IndexDataAnalyser/dashboard/historical_data.html`
- **API Endpoint**: `http://localhost:5000/api`

## 🔧 Systemd Services (Optional)

If you enabled systemd during setup:

```bash
# Enable auto-start
sudo systemctl enable oi-dashboard-api
sudo systemctl enable oi-data-collector

# Start services
sudo systemctl start oi-dashboard-api
sudo systemctl start oi-data-collector

# Check status
sudo systemctl status oi-dashboard-api
```

## 🐛 Troubleshooting

### Services Won't Start
```bash
# Check logs
cat logs/api.log
cat logs/data_collector.log

# Check MySQL
sudo systemctl status mysql

# Test database connection
mysql -u root -p analyzer_db
```

### Permission Denied
```bash
chmod +x setup.sh start.sh stop.sh status.sh
```

### Port Already in Use
```bash
# Check what's using port 5000
sudo netstat -tlnp | grep 5000

# Kill the process
sudo kill <PID>
```

## 📋 Checklist

- [ ] Run `./setup.sh`
- [ ] Edit `.env` with your credentials
- [ ] Run `./start.sh`
- [ ] Access dashboard in browser
- [ ] Verify API health: `curl http://localhost:5000/api/health`
- [ ] Check status: `./status.sh`

## 🎯 Next Steps

1. **Production Deployment**: See `DEPLOYMENT.md` for Nginx setup
2. **Monitoring**: Set up log rotation and monitoring
3. **Backups**: Schedule regular database backups
4. **Security**: Configure firewall and SSL

---

For detailed documentation, see [DEPLOYMENT.md](DEPLOYMENT.md)
