# Quick Start Guide

Get the Index Data Analyser dashboard running in **5 minutes**!

## Prerequisites

- ✅ Python 3.8 or higher
- ✅ MySQL 8.0 or higher running
- ✅ Dhan trading account with API access

## Step-by-Step Setup

### Step 1: Install Python Dependencies (1 minute)

Open terminal in project root and run:

```bash
pip install -r requirements.txt
```

Expected output:
```
Successfully installed dhanhq-2.0.0 flask-3.0.0 mysql-connector-python-8.0.33 ...
```

### Step 2: Configure Credentials (1 minute)

Edit the `.env` file with your details:

```env
# Get these from Dhan portal
DHAN_CLIENT_ID=1234567890
DHAN_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbG...

# Your MySQL password
DB_PASSWORD=your_mysql_password
```

**Where to find Dhan credentials:**
1. Login to https://dhan.co
2. Go to Settings → API Access
3. Generate Access Token (valid for 24 hours)

### Step 3: Setup Database (30 seconds)

Run the setup script:

```bash
python setup_database.py
```

Expected output:
```
✅ Connected to MySQL successfully
✅ Created table: market_feed_realtime (77 columns)
✅ Database setup complete
```

### Step 4: Start Data Collection (30 seconds)

Open **Terminal 1** and run:

```bash
python main.py
```

Expected output:
```
INFO - Starting Index Data Analyser...
INFO - Database pool initialized (5 connections)
INFO - Connected to Dhan API successfully
INFO - WebSocket connected successfully
INFO - Subscribed to 2 instruments (NIFTY 50, INDIA VIX)
INFO - Starting data collection loop...
```

✅ **Keep this terminal running** - it collects live data

### Step 5: Start Dashboard API (30 seconds)

Open **Terminal 2** and run:

```bash
cd dashboard
python api.py
```

Expected output:
```
INFO - Starting OI Dashboard API server...
 * Running on http://0.0.0.0:5000
```

✅ **Keep this terminal running** - it serves dashboard data

### Step 6: Open Dashboard (10 seconds)

**Option A: File Explorer**
1. Navigate to `dashboard` folder
2. Double-click `index.html`

**Option B: Command Line**
```bash
# Windows
start dashboard/index.html

# macOS
open dashboard/index.html

# Linux
xdg-open dashboard/index.html
```

## You're Done! 🎉

You should now see:

```
┌─────────────────────────────────────────────────┐
│  NIFTY 50: 22,040.50 (+0.5%)                    │
│  ATM STRIKE: 22,000                             │
│  INDIA VIX: 16.00                               │
│  15-Min Move: ±88 pts | 5-Min Move: ±51 pts    │
├─────────────────────────────────────────────────┤
│  STRIKE │ CALLS (CE) │ PUTS (PE) │ ... →       │
│  25200  │ 45.2L      │ 38.1L     │             │
│  25250  │ 42.8L      │ 39.5L     │             │
│  ...                                            │
└─────────────────────────────────────────────────┘
```

## Navigation

- **Dashboard** (index.html) - OI Difference Live with time-series
- **Option Chain** (option_chain.html) - Traditional option chain view

Click the sidebar links to switch between views.

## Troubleshooting

### ❌ "Failed to fetch data"

**Problem**: Dashboard can't connect to API

**Solution**:
```bash
# Check if API is running
# Terminal 2 should show: "Running on http://0.0.0.0:5000"

# If not, restart it:
cd dashboard
python api.py
```

### ❌ "No data available"

**Problem**: Database is empty

**Solution**:
```bash
# Make sure main.py is running
# Terminal 1 should show: "Fetched option chain data"

# Wait 1-2 minutes for data to accumulate
```

### ❌ "Authentication Failed"

**Problem**: Invalid or expired access token

**Solution**:
1. Login to https://dhan.co
2. Settings → API Access → Generate New Token
3. Copy new token
4. Update `.env` file: `DHAN_ACCESS_TOKEN=new_token_here`
5. Restart `python main.py`

### ❌ "Access denied for user"

**Problem**: Wrong MySQL password

**Solution**:
1. Check MySQL password: Try logging in with `mysql -u root -p`
2. Update `.env`: `DB_PASSWORD=correct_password`
3. Restart `python main.py`

### ❌ "Connection refused" (Port 3306)

**Problem**: MySQL is not running

**Solution**:
```bash
# Windows
net start MySQL80

# macOS
brew services start mysql

# Linux
sudo systemctl start mysql
```

## What's Happening?

### Terminal 1 (main.py)
- ✅ Collects live option chain data every 60 seconds
- ✅ Streams real-time NIFTY & VIX prices via WebSocket
- ✅ Stores everything in MySQL database
- ✅ Automatically pauses outside market hours

### Terminal 2 (dashboard/api.py)
- ✅ Serves REST API on port 5000
- ✅ Fetches data from database
- ✅ Calculates OI differences
- ✅ Provides data to dashboard

### Browser (dashboard/*.html)
- ✅ Fetches live data from API
- ✅ Updates every 3-5 seconds
- ✅ Shows OI changes, Greeks, signals
- ✅ Calculates volatility metrics

## Next Steps

1. **Explore the Dashboard**:
   - Scroll horizontally to see time-series data
   - Click "Jump to Latest" for most recent data
   - Switch between Dashboard and Option Chain views

2. **Customize Settings**:
   - Edit `.env` to change update intervals
   - Adjust strike range: `STRIKE_RANGE=750`
   - Change fetch interval: `DATA_FETCH_INTERVAL=60`

3. **View Logs**:
   - Check `api_server.log` for API logs
   - Monitor Terminal 1 for data collection status

4. **Read Documentation**:
   - [README.md](README.md) - Full features and configuration
   - [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Code organization
   - [docs/OI_DASHBOARD_README.md](docs/OI_DASHBOARD_README.md) - Dashboard details

## Tips for Best Results

✅ **Run during market hours** (9:15 AM - 3:30 PM IST) for live data
✅ **Keep both terminals running** for continuous updates
✅ **Regenerate access token daily** (Dhan tokens expire in 24 hours)
✅ **Check database size** regularly if running long-term
✅ **Use Chrome/Firefox** for best dashboard performance

## Common Questions

**Q: Can I run this on a remote server?**
A: Yes! Just ensure MySQL and Python are installed, and access the dashboard via the server's IP.

**Q: How much data is stored?**
A: ~1 row per strike per minute = ~50-100 rows/minute during market hours.

**Q: Does it work with BANKNIFTY?**
A: Code is for NIFTY, but can be modified in `core/option_chain.py` to support BANKNIFTY.

**Q: Can I export data to Excel?**
A: Yes, query the `nifty_oc_historical` table directly or add export functionality.

## Need Help?

- 📖 Check [README.md](README.md) for detailed docs
- 🐛 Review troubleshooting section above
- 💬 Open an issue on GitHub
- 📧 Contact support

---

**Happy Trading! 📈**
