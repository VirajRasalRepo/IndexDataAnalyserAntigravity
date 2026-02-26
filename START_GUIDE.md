# How to Start the Application

## Current Status ✅

### What's Working:
- ✅ **Database**: Has 11,098 rows of option chain data
- ✅ **Dashboard API**: Running on port 5000
- ✅ **NIFTY Data**: Displaying correctly (Spot: 25,498.30, +0.29%)
- ✅ **OI Difference**: Time-series data available
- ✅ **Option Chain**: Full CE/PE data with Greeks

### Known Issue:
- ⚠️ **INDIA VIX**: Not showing (WebSocket not storing to `market_feed_realtime` table)
  - This is a known issue that requires investigation
  - Dashboard works without VIX (shows "N/A")

## Start Commands

### Terminal 1: Data Collection
```bash
python main.py
```
**Expected Output:**
```
INFO - Database connection pool initialized
INFO - Dhan API client initialized
INFO - WebSocket connected successfully
INFO - Subscribed to 9 instruments
INFO - Iteration 1: Stored 31 strikes (Spot: 25500.50)
```

### Terminal 2: Dashboard API
```bash
cd dashboard
python api.py
```
**Expected Output:**
```
INFO - Starting OI Dashboard API server...
 * Running on http://0.0.0.0:5000
```

### Browser: Open Dashboard
```bash
# Windows
start dashboard/index.html

# Or manually:
# Open: d:\Pycharm\Clone\IndexDataAnalyser\dashboard\index.html
```

## Verification

### 1. Check API Health
```bash
curl http://localhost:5000/api/health
```
**Expected:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-26T09:24:37.237333"
}
```

### 2. Check NIFTY Data
```bash
curl http://localhost:5000/api/spot-price
```
**Expected:**
```json
{
  "nifty": {
    "value": 25498.30,
    "change_pct": 0.29,
    "timestamp": "2026-02-26 09:24:54"
  }
}
```

### 3. Check OI Data
```bash
curl "http://localhost:5000/api/oi-difference-live?strike_count=10"
```
**Should return:** JSON with strikes and time_series data

## Dashboard Features

### Main Dashboard (index.html)
- **NIFTY 50 Card**: Shows current spot price and % change ✅
- **ATM Strike Card**: Shows at-the-money strike price ✅
- **VIX Card**: Shows "N/A" until WebSocket stores data ⚠️
- **OI Difference Table**: Shows 3-minute interval time-series ✅
  - Vertical scroll: See more strikes
  - Horizontal scroll: See historical time periods
  - "Jump to Latest": Go to most recent data

### Option Chain View (option_chain.html)
- Full option chain with CE/PE data ✅
- OI, Volume, IV, LTP, Delta, Greeks ✅
- BULLISH/BEARISH/NEUTRAL signals ✅

## Troubleshooting

### Issue: Dashboard shows "Failed to fetch data"

**Check:**
```bash
# Is API running?
curl http://localhost:5000/api/health

# If not, restart:
cd dashboard
python api.py
```

### Issue: Dashboard shows old data

**Solution:**
- Main.py must be running to collect new data
- Data updates every 60 seconds
- Refresh browser (F5)

### Issue: "No data for latest timestamp"

**Check Database:**
```bash
python -c "
from core.database import DatabaseManager
DatabaseManager.initialize_pool(pool_size=1)
with DatabaseManager.get_cursor() as cursor:
    cursor.execute('SELECT COUNT(*) FROM nifty_oc_historical')
    print(f'Rows: {cursor.fetchone()[0]}')
"
```

If 0 rows: Run `python main.py` to collect data

### Issue: VIX shows "N/A"

**Known Issue:**
- WebSocket is not storing data to `market_feed_realtime` table
- This is a current limitation
- Dashboard works without VIX
- To be fixed in future update

## API Endpoints Summary

| Endpoint | Status | Description |
|----------|--------|-------------|
| `/api/health` | ✅ | Health check |
| `/api/spot-price` | ✅ | NIFTY spot price (VIX missing) |
| `/api/option-chain` | ✅ | Full option chain data |
| `/api/expiry-dates` | ✅ | Available dates from DB |
| `/api/oi-difference-live` | ✅ | Time-series OI difference |

## Quick Commands

```bash
# Check if API is running
ps aux | grep "python.*api.py"

# Check if main.py is running
ps aux | grep "python.*main.py"

# View API logs
tail -f api_server.log

# View main.py output
# (Check terminal where main.py is running)

# Kill API if stuck
pkill -f "python.*api.py"

# Restart API
cd dashboard && python api.py &
```

## Next Steps

1. ✅ Dashboard API is running → Open dashboard/index.html
2. ✅ Data is being collected → main.py is running
3. ⚠️ VIX issue → To be investigated (non-critical)

**Dashboard is functional and ready to use!**
