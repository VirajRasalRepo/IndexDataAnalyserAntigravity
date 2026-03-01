# WebSocket/Webhook Issues - Fixed

## 🐛 Issues Identified

### 1. Database Schema Mismatch (CRITICAL)

**Problem**: The `setup_database.sql` created a normalized table schema with `symbol` column, but the WebSocket code expects a wide-format schema with individual columns for each instrument.

**Impact**: WebSocket data insertion would fail, preventing real-time market data from being stored.

**Location**:
- `setup_database.sql` (lines 58-89)
- `streaming/market_feed_websocket.py` (lines 329-400)

**Root Cause**: The deployment setup script used a different schema design than what the existing WebSocket code requires.

---

### 2. API Query Using Wrong Column Names (CRITICAL)

**Problem**: The API was querying `market_feed_realtime` table using incorrect column names (`symbol`, `close_price`, `last_update_time`) that don't exist in the actual schema.

**Impact**: VIX data would not be fetched, causing the dashboard to show incomplete market information.

**Location**: `dashboard/api.py` (lines 122-139)

**Root Cause**: API code was written for a normalized schema, but WebSocket uses wide-format schema.

---

## ✅ Fixes Applied

### Fix 1: Updated Database Schema

**File**: `setup_database.sql`

**Changes**:
- Replaced normalized schema (with `symbol` column) with wide-format schema
- Added individual columns for each instrument:
  - `india_vix_ltp`, `india_vix_volume`, `india_vix_open`, `india_vix_high`, `india_vix_low`, `india_vix_close`
  - `nifty_50_ltp`, `nifty_50_volume`, etc.
  - `reliance_ltp`, `reliance_volume`, `reliance_avg_price`, `reliance_total_buy_qty`, `reliance_total_sell_qty`
  - Similar columns for HDFC Bank, ICICI Bank, Infosys, TCS, ITC, L&T
- Changed timestamp column from `last_update_time` to `timestamp`
- Removed INSERT statements for default symbols (not needed in wide format)

**New Schema**:
```sql
CREATE TABLE IF NOT EXISTS market_feed_realtime (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),

    -- India VIX columns
    india_vix_ltp DECIMAL(10, 2),
    india_vix_volume BIGINT,
    india_vix_open DECIMAL(10, 2),
    india_vix_high DECIMAL(10, 2),
    india_vix_low DECIMAL(10, 2),
    india_vix_close DECIMAL(10, 2),

    -- Additional instruments...
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB;
```

---

### Fix 2: Updated API VIX Query

**File**: `dashboard/api.py`

**Changes**:
- Updated column names: `close_price` → `india_vix_close`, `india_vix_ltp`
- Removed WHERE clause with `symbol` filter
- Updated ORDER BY: `last_update_time` → `timestamp`
- Added proper VIX change percentage calculation using close and LTP
- Added debug logging for VIX data unavailability

**Old Query**:
```python
SELECT close_price
FROM market_feed_realtime
WHERE symbol = 'INDIA VIX'
ORDER BY last_update_time DESC
LIMIT 1
```

**New Query**:
```python
SELECT india_vix_close, india_vix_ltp
FROM market_feed_realtime
ORDER BY timestamp DESC
LIMIT 1
```

**New Logic**:
```python
vix_close = decimal_to_float(vix_result[0])
vix_ltp = decimal_to_float(vix_result[1]) if vix_result[1] else vix_close

# Calculate change percentage
if vix_close and vix_close > 0:
    change_pct = ((vix_ltp - vix_close) / vix_close) * 100

vix_data = {
    'value': vix_ltp,
    'change_pct': round(change_pct, 2)
}
```

---

## 🔍 WebSocket Data Flow

### How It Works Now:

1. **WebSocket Connection**:
   ```
   DhanMarketFeed → connects to wss://api-feed.dhan.co
   └─ Subscribes to 9 instruments (NIFTY, VIX, RELIANCE, HDFC, ICICI, INFY, TCS, ITC, L&T)
   ```

2. **Data Reception**:
   ```
   Binary Message → _parse_quote_packet()
   └─ Extracts: LTP, Volume, OHLC, Buy/Sell Qty
   └─ Stores in memory: self.market_data[instrument_key]
   ```

3. **Database Storage** (`store_to_database()` in main.py):
   ```
   Every 4 seconds (DATA_FETCH_INTERVAL):
   └─ Collect data from all instruments
   └─ Build row with columns: india_vix_ltp, nifty_50_ltp, reliance_ltp, etc.
   └─ INSERT INTO market_feed_realtime
   ```

4. **API Retrieval**:
   ```
   GET /api/spot-price
   └─ Fetches latest VIX from market_feed_realtime
   └─ Returns VIX value and change percentage
   ```

---

## 📊 Schema Comparison

### Wide Format (CORRECT - Now Used)
```
| timestamp           | india_vix_ltp | nifty_50_ltp | reliance_ltp | ... |
|---------------------|---------------|--------------|--------------|-----|
| 2026-03-01 10:15:00 | 13.25         | 25303.90     | 2850.50      | ... |
```

**Advantages**:
- ✅ Single row per timestamp
- ✅ Fast queries (no joins needed)
- ✅ Matches WebSocket code expectations
- ✅ Easy to fetch all instruments at once

**Disadvantages**:
- ❌ Wide table (many columns)
- ❌ Hard to add new instruments

---

### Normalized Format (INCORRECT - Previously Created)
```
| id | symbol      | ltp      | timestamp           |
|----|-------------|----------|---------------------|
| 1  | INDIA VIX   | 13.25    | 2026-03-01 10:15:00 |
| 2  | NIFTY       | 25303.90 | 2026-03-01 10:15:00 |
```

**Advantages**:
- ✅ Normalized design
- ✅ Easy to add new instruments
- ✅ Smaller row size

**Disadvantages**:
- ❌ Multiple rows per timestamp
- ❌ Requires joins for multi-instrument queries
- ❌ **Doesn't match WebSocket code** (BREAKING)

---

## 🧪 Testing the Fix

### 1. Recreate Database

```bash
# Drop existing table
mysql -u root -p analyzer_db -e "DROP TABLE IF EXISTS market_feed_realtime;"

# Run updated setup script
mysql -u root -p < setup_database.sql
```

### 2. Verify Schema

```sql
USE analyzer_db;
DESCRIBE market_feed_realtime;

-- Expected columns:
-- id, timestamp,
-- india_vix_ltp, india_vix_volume, india_vix_open, india_vix_high, india_vix_low, india_vix_close,
-- nifty_50_ltp, nifty_50_volume, nifty_50_open, nifty_50_high, nifty_50_low, nifty_50_close,
-- etc. for all 9 instruments
```

### 3. Test WebSocket

```bash
# Start services
./start.sh

# Check logs
tail -f logs/data_collector.log

# Look for:
# - "WebSocket connected successfully"
# - "Subscribed to 9 instruments in Quote mode"
# - "Received data for IDX_I_13: LTP=..."
# - "Stored market data for X instruments"
```

### 4. Test API

```bash
# Test VIX endpoint
curl http://localhost:5000/api/spot-price

# Expected response:
{
  "nifty": {
    "value": 25303.90,
    "change_pct": 0.45,
    "timestamp": "2026-03-01 10:15:00"
  },
  "vix": {
    "value": 13.25,
    "change_pct": -2.15
  }
}
```

### 5. Verify Database

```sql
-- Check if data is being inserted
SELECT * FROM market_feed_realtime ORDER BY timestamp DESC LIMIT 1;

-- Should show latest timestamp with all columns populated
```

---

## 📝 Code Locations Reference

### WebSocket Implementation
- **Main Class**: `streaming/market_feed_websocket.py` → `DhanMarketFeed`
- **Connection**: Lines 86-109
- **Subscription**: Lines 200-224
- **Data Parsing**: Lines 226-317
- **Database Storage**: Lines 329-400

### Integration in Main Pipeline
- **Initialization**: `main.py` lines 104-108
- **Storage Trigger**: `main.py` lines 149-155
- **Runs every**: 4 seconds (Config.DATA_FETCH_INTERVAL)

### API Usage
- **VIX Fetch**: `dashboard/api.py` lines 122-142
- **Endpoint**: GET `/api/spot-price`
- **Used in**: Dashboard header for VIX display

---

## ⚠️ Important Notes

1. **Schema Must Match**: The `market_feed_realtime` table schema MUST use wide format with individual columns for each instrument. Do not change to normalized format.

2. **Column Naming**: Column names must follow the pattern: `{prefix}_{field}` where:
   - `prefix` matches `INSTRUMENTS` in `market_feed_websocket.py` (line 52-62)
   - `field` is one of: `ltp`, `volume`, `open`, `high`, `low`, `close`, `avg_price`, `total_buy_qty`, `total_sell_qty`

3. **New Instruments**: To add new instruments:
   - Add to `INSTRUMENTS` list in `market_feed_websocket.py`
   - Add columns to `market_feed_realtime` table: `ALTER TABLE market_feed_realtime ADD COLUMN new_instrument_ltp DECIMAL(10,2), ...`

4. **Timestamp Column**: Always use `timestamp` (not `last_update_time`) for consistency.

---

## ✅ Status: FIXED

All WebSocket/webhook issues have been resolved:
- ✅ Database schema matches WebSocket code
- ✅ API queries use correct column names
- ✅ VIX data will be fetched successfully
- ✅ Real-time market data will be stored properly
- ✅ Dashboard will display complete market information

**Last Updated**: 2026-03-01
**Version**: 1.0
