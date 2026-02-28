# WebSocket Real-Time Market Feed Setup Guide

## Overview

Your application now includes **real-time market data streaming** via WebSocket! This provides:

- ✅ **Real-time LTP updates** (every few seconds)
- ✅ **OHLC data** (Open, High, Low, Close)
- ✅ **Volume and trade quantities**
- ✅ **Buy/Sell pressure indicators**
- ✅ **Average trade prices**
- ✅ **Much more efficient** (one connection for all instruments)

## Setup Steps

### Step 1: Install Dependencies

```bash
pip install websocket-client
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

### Step 2: Create Database Table

Run this SQL in your MySQL database:

```sql
-- Copy and paste the entire content from schema_market_feed.sql
-- Or run: mysql -u root -p analyzer_db < schema_market_feed.sql
```

**Quick SQL:**
```bash
mysql -u root -p analyzer_db < schema_market_feed.sql
```

Or manually in MySQL:
```sql
USE analyzer_db;
SOURCE d:\Pycharm\Clone\IndexDataAnalyser\schema_market_feed.sql;
```

### Step 3: Run the Application

```bash
python main.py
```

## What Happens Now

### Real-Time Data Flow

1. **WebSocket Connection**: Automatically connects to Dhan's live market feed
2. **Subscription**: Subscribes to Quote Packet (Mode 4) for all 9 instruments
3. **Streaming**: Receives real-time updates continuously
4. **Storage**: Stores comprehensive data every 4 seconds

### Data Storage

**Table: `market_feed_realtime`**
   - LTP, Volume, OHLC
   - Average price, Buy/Sell quantities
   - Real-time updates via WebSocket
   - Single WebSocket connection for all instruments

## Application Logs

You'll see logs like:

```
2026-02-25 10:30:15 - market_feed_websocket - INFO - WebSocket connected successfully
2026-02-25 10:30:15 - market_feed_websocket - INFO - Subscribed to 9 instruments in Quote mode
2026-02-25 10:30:15 - __main__ - INFO - Real-time market feed WebSocket started
2026-02-25 10:30:19 - __main__ - INFO - Real-time feed: Stored data for 9 instruments
2026-02-25 10:30:23 - __main__ - INFO - Real-time feed: Stored data for 9 instruments
```

## Data Fields Available

### For All Instruments:
- **LTP** (Last Traded Price)
- **Volume** (Total traded volume)
- **Open** (Opening price)
- **High** (Day's high)
- **Low** (Day's low)
- **Close** (Closing/current price)

### Additional for Equity Stocks (not indices):
- **Average Price** (Average traded price)
- **Total Buy Quantity** (Cumulative buy side)
- **Total Sell Quantity** (Cumulative sell side)

## Query Examples

### Get Latest Real-Time Data:
```sql
SELECT
    timestamp,
    nifty_50_ltp,
    reliance_ltp,
    hdfc_bank_ltp,
    icici_bank_ltp
FROM market_feed_realtime
ORDER BY id DESC
LIMIT 1;
```

### Get OHLC for Reliance:
```sql
SELECT
    timestamp,
    reliance_open,
    reliance_high,
    reliance_low,
    reliance_close,
    reliance_ltp
FROM market_feed_realtime
WHERE DATE(timestamp) = CURDATE()
ORDER BY timestamp DESC
LIMIT 10;
```

### Calculate Buy/Sell Pressure:
```sql
SELECT
    timestamp,
    reliance_ltp,
    reliance_total_buy_qty,
    reliance_total_sell_qty,
    (reliance_total_buy_qty - reliance_total_sell_qty) AS net_pressure
FROM market_feed_realtime
WHERE DATE(timestamp) = CURDATE()
ORDER BY timestamp DESC
LIMIT 20;
```

### Intraday Price Movement:
```sql
SELECT
    timestamp,
    nifty_50_ltp,
    nifty_50_volume,
    (nifty_50_ltp - nifty_50_open) AS price_change,
    ((nifty_50_ltp - nifty_50_open) / nifty_50_open * 100) AS pct_change
FROM market_feed_realtime
WHERE DATE(timestamp) = CURDATE()
ORDER BY timestamp;
```

## Troubleshooting

### WebSocket Connection Issues

**Problem**: `WebSocket connection failed`

**Solution**:
1. Check internet connection
2. Verify access token is valid (tokens expire)
3. Check Dhan API status

### No Data Being Received

**Problem**: WebSocket connected but no data

**Solution**:
1. Ensure market is open (9:15 AM - 3:30 PM IST)
2. Check logs for subscription errors
3. Verify security IDs are correct

### Database Errors

**Problem**: `Table 'market_feed_realtime' doesn't exist`

**Solution**:
```bash
mysql -u root -p analyzer_db < schema_market_feed.sql
```

## Architecture

### Real-Time WebSocket Flow:
```
Main Loop (4s):
  ├─ Sync Trades (every 60s)
  ├─ Fetch Option Chain Data
  └─ Store WebSocket Data → market_feed_realtime
       ↑
WebSocket (Background Thread) → Continuous Streaming
```

## Performance Benefits

| Feature | WebSocket Implementation |
|---------|-------------------------|
| **API Calls/min** | 0 (streaming only) |
| **Latency** | Real-time (<1 second) |
| **Data Points** | 9+ fields per instrument |
| **Connections** | 1 WebSocket for all instruments |
| **Efficiency** | Minimal bandwidth, maximum data |

## Next Steps

1. ✅ **Run the application** - Test during market hours
2. ✅ **Query the data** - Use SQL examples above
3. ✅ **Build dashboards** - Use real-time data for visualization
4. ✅ **Create alerts** - Set up price/volume alerts
5. ✅ **Analyze patterns** - Study buy/sell pressure

## Advanced Usage

### Add More Instruments

Edit `market_feed_websocket.py`:

```python
INSTRUMENTS = [
    # ... existing instruments ...
    {"security_id": 3456, "exchange_segment": "NSE_EQ", "prefix": "new_stock"},
]
```

Then update the SQL schema to add columns for the new instrument.

### Change Update Frequency

In `main.py`, adjust:
```python
time.sleep(Config.DATA_FETCH_INTERVAL)  # Currently 4 seconds
```

### Subscribe to Full Packet (Market Depth)

In `market_feed_websocket.py`, change:
```python
QUOTE_MODE = 4  # Change to 8 for Full Packet
```

## Support

For issues or questions:
- Check logs in the console
- Review [Dhan API Documentation](https://dhanhq.co/docs/v2/)
- Open an issue in the repository

---

🚀 **You now have enterprise-grade real-time market data streaming!**
