# Greeks Dashboard - Startup & Testing Guide

## 🚀 Quick Start

### Step 1: Start the Data Collector

```bash
python main.py
```

**Expected Output:**
```
2026-03-04 09:15:00 - __main__ - INFO - Database connection pool initialized
2026-03-04 09:15:00 - __main__ - INFO - Dhan API client initialized
2026-03-04 09:15:00 - __main__ - INFO - Using expiry date: 2026-03-06
2026-03-04 09:15:00 - __main__ - INFO - Real-time market feed WebSocket started
2026-03-04 09:15:04 - __main__ - INFO - Iteration 1: Stored 30 strikes (Spot: 24500.00)
2026-03-04 09:15:04 - __main__ - INFO - Real-time feed: Stored data for 9 instruments
2026-03-04 09:15:04 - __main__ - INFO - Greeks: Bias=BULLISH, Net Δ=0.125, Alerts=2
```

### Step 2: Start the API Server

Open a new terminal:

```bash
cd dashboard
python api.py
```

**Expected Output:**
```
2026-03-04 09:16:00 - __main__ - INFO - Starting OI Dashboard API server...
 * Serving Flask app 'api'
 * Running on http://0.0.0.0:5000
```

### Step 3: Open the Greeks Dashboard

```bash
start dashboard/greeks.html
```

Or manually open: `http://localhost:5000/greeks.html` in your browser

---

## ✅ Testing Checklist

### 1. Test API Endpoints

**Test Health Check:**
```bash
curl http://localhost:5000/api/health
```

Expected: `{"status":"healthy","timestamp":"2026-03-04T09:16:00.000Z"}`

**Test Greeks Pro Endpoint:**
```bash
curl http://localhost:5000/api/greeks-pro
```

Expected: JSON with:
- `status: "ok"`
- `spot`, `vix`, `dte`, `iv_rank`
- `trend_intensity` (market_bias, net_delta_flow)
- `ce_top5`, `pe_top5` arrays
- `alerts`, `entry_signals` arrays

**Test Portfolio Endpoint:**
```bash
curl http://localhost:5000/api/greeks/portfolio
```

Expected: JSON with:
- `total_delta`: 0.0 (if no trades)
- `delta_bias`: "NEAR NEUTRAL"
- `open_trades`: 0
- `trades`: []

### 2. Verify Database Schema

```sql
-- Check Greeks columns exist
USE analyzer_db;

SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'nifty_oc_historical'
  AND COLUMN_NAME LIKE '%efficiency%';

-- Expected: 4 rows (ce_efficiency, ce_vega_adj_efficiency, pe_efficiency, pe_vega_adj_efficiency)

-- Check User_ table
DESCRIBE User_;

-- Expected: 11 columns (trade_id, strike_price, option_type, quantity, etc.)
```

### 3. Verify Greeks Processing in Logs

Check `main.py` logs for:

```
Greeks: Bias=BULLISH, Net Δ=0.125, Alerts=2
```

This confirms:
- ✅ Greeks processor is running
- ✅ Market bias calculated
- ✅ Net delta flow computed
- ✅ Alerts detected

### 4. Test Dashboard UI

Open `http://localhost:5000/greeks.html` and verify:

**Metrics Display:**
- ✅ NIFTY Spot price shows current value
- ✅ India VIX shows with % change
- ✅ Days to Expiry shows correct DTE
- ✅ Market Bias shows BULLISH/BEARISH/NEUTRAL
- ✅ IV Rank shows percentage (0-100)
- ✅ PCR shows Put-Call Ratio

**Tables Display:**
- ✅ Top 5 CE strikes table populated
- ✅ Top 5 PE strikes table populated
- ✅ Efficiency scores visible
- ✅ Alert badges show (Theta Trap, Gamma Blast, etc.)

**Real-Time Updates:**
- ✅ "Last Update" timestamp changes every 60 seconds
- ✅ Live indicator pulses (green dot)
- ✅ Data refreshes automatically

---

## 🐛 Troubleshooting

### Issue: "No data available for today"

**Cause:** No option chain data in database for current date

**Solution:**
```bash
# Check if data exists
mysql -u root -p analyzer_db -e "SELECT COUNT(*) FROM nifty_oc_historical WHERE Date = CURDATE();"

# If 0, wait for main.py to run during market hours (9:15 AM - 3:30 PM IST)
```

### Issue: "Connection error. Is the API running?"

**Cause:** API server not started or wrong port

**Solution:**
```bash
# Check if API is running
curl http://localhost:5000/api/health

# If fails, restart API
cd dashboard
python api.py
```

### Issue: Greeks columns not found

**Cause:** Database schema not updated

**Solution:**
```bash
# Re-run schema update
python apply_greeks_schema.py

# Verify columns added
mysql -u root -p analyzer_db -e "DESCRIBE nifty_oc_historical;" | grep efficiency
```

### Issue: "Invalid ACTIVE_EXPIRY format"

**Cause:** Wrong date format in .env

**Solution:**
```bash
# Edit .env file
ACTIVE_EXPIRY=2026-03-06  # Must be YYYY-MM-DD format

# Restart main.py
```

### Issue: All efficiency values are NULL

**Cause:** Greeks processor not running or data not being processed

**Solution:**
1. Check main.py logs for "Greeks: Bias=..." messages
2. Verify option chain data exists in database
3. Ensure market is open (9:15 AM - 3:30 PM IST on trading days)

---

## 📊 Sample Data Verification

### Check Latest Greeks Data

```sql
SELECT
    strike_price,
    ce_efficiency,
    ce_rank_label,
    ce_alert_theta_trap,
    pe_efficiency,
    pe_rank_label,
    market_bias,
    net_delta_flow
FROM nifty_oc_historical
WHERE Date = CURDATE()
  AND Time = (SELECT MAX(Time) FROM nifty_oc_historical WHERE Date = CURDATE())
LIMIT 10;
```

**Expected Output:**
```
strike_price | ce_efficiency | ce_rank_label | ce_alert_theta_trap | pe_efficiency | pe_rank_label | market_bias | net_delta_flow
24400       | 2.45          | ITM           | 0                   | 1.23          | OTM           | BULLISH     | 0.125
24450       | 3.12          | ATM           | 0                   | 2.87          | ATM           | BULLISH     | 0.125
24500       | 2.98          | ATM           | 0                   | 3.45          | ITM           | BULLISH     | 0.125
```

### Add Sample Portfolio Trade

```sql
-- Add a test trade
INSERT INTO User_ (strike_price, option_type, quantity, entry_price, notes)
VALUES (24500, 'CE', 50, 120.50, 'Test trade for Greeks dashboard');

-- Verify portfolio endpoint shows it
```

Then check: `http://localhost:5000/api/greeks/portfolio`

Expected:
```json
{
  "total_delta": 22.5,
  "delta_bias": "NET LONG",
  "pnl_estimate": 1250.00,
  "open_trades": 1,
  "trades": [...]
}
```

---

## ⚙️ Configuration Management

### Weekly Update: ACTIVE_EXPIRY

**Every Thursday 3:30 PM+**, update the expiry date:

1. Edit `.env`:
```bash
ACTIVE_EXPIRY=2026-03-13  # Next week's expiry
```

2. Restart applications:
```bash
# Stop main.py (Ctrl+C)
# Stop api.py (Ctrl+C)

# Restart
python main.py
cd dashboard && python api.py
```

### Enable Debug Mode

For testing outside market hours:

```bash
# In .env
DEBUG=True

# This allows main.py to run even outside market hours
```

---

## 📈 Expected Behavior

### During Market Hours (9:15 AM - 3:30 PM IST)

**main.py:**
- Fetches option chain data every 4 seconds
- Processes Greeks analytics
- Logs: "Greeks: Bias=..., Net Δ=..., Alerts=..."
- Stores data to database

**API:**
- `/api/greeks-pro` returns fresh data
- Updates every time main.py processes new data

**Dashboard:**
- Auto-refreshes every 60 seconds
- Shows live metrics
- Displays alerts and signals

### Outside Market Hours

**main.py:**
- Performs post-market sync once
- Calculates next market open time
- Sleeps until 30 minutes before market open
- Logs: "Market closed. Next market open: 2026-03-04 09:15:00"

**API:**
- Still serves last available data from database
- `/api/greeks-pro` works but data is from market close

**Dashboard:**
- Shows last available data
- Timestamp shows market close time
- No real-time updates until market reopens

---

## 🎯 Performance Benchmarks

**API Response Times (Expected):**
- `/api/health`: < 10ms
- `/api/greeks-pro`: 100-300ms (includes DB queries + Greeks calculations)
- `/api/greeks/portfolio`: 50-100ms

**main.py Processing (Expected):**
- Option chain fetch + store: 200-500ms
- Greeks processing: 50-150ms
- Total iteration time: ~4 seconds (Config.DATA_FETCH_INTERVAL)

**Dashboard Load Time:**
- Initial page load: < 500ms
- Data fetch: 100-300ms
- Total ready time: < 1 second

---

## 📝 Logs to Monitor

### main.py

```
✅ Greeks: Bias=BULLISH, Net Δ=0.125, Alerts=2
✅ Iteration 123: Stored 30 strikes (Spot: 24500.00)
✅ Real-time feed: Stored data for 9 instruments
```

### api.py

```
✅ INFO - "GET /api/greeks-pro HTTP/1.1" 200 -
✅ INFO - "GET /api/greeks/portfolio HTTP/1.1" 200 -
```

### Browser Console (greeks.html)

```
✅ Fetched Greeks data successfully
✅ Updated dashboard at 14:32:15
```

---

## 🚀 Production Deployment

See [docs/GREEKS_INTEGRATION.md](GREEKS_INTEGRATION.md) for full production deployment guide.

**Quick Production Checklist:**
- [ ] Database schema updated (`python apply_greeks_schema.py`)
- [ ] ACTIVE_EXPIRY configured in .env
- [ ] main.py running (systemd service recommended)
- [ ] api.py running (systemd service recommended)
- [ ] Firewall allows port 5000 (if needed)
- [ ] Weekly cron job to update ACTIVE_EXPIRY (optional)

---

**Last Updated:** March 3, 2026
**Status:** Ready for Testing
