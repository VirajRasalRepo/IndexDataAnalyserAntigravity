# Greeks Dashboard Integration Guide

## Overview

The Greeks analytics engine has been integrated into your IndexDataAnalyser application. This provides professional-grade options trading insights using Dhan's pre-calculated Greeks data.

## ✅ Completed (Phase 1)

### 1. Core Greeks Processor (`core/greeks_processor.py`)

Created a production-ready Greeks processing engine that:

- ✅ Uses **Dhan pre-calculated Greeks** (NO Black-Scholes calculations)
- ✅ Calculates **Efficiency Score** (Delta / |Theta|)
- ✅ Calculates **Vega-adjusted Efficiency**
- ✅ Tracks **Greeks Velocity** (rate of change per minute)
- ✅ Detects **Theta Trap**, **Gamma Blast**, **Negative Carry** conditions
- ✅ Calculates **Trend Intensity** and **Market Bias**
- ✅ Detects **PCR-Delta Divergence** signals
- ✅ Generates **Entry/Exit/Caution signals**
- ✅ **Charm defaults to 0.0** if not in Dhan API response

**Key Functions:**
```python
from core.greeks_processor import process_greeks_from_db

# Process Greeks from database rows
result = process_greeks_from_db(
    db_rows=db_rows,           # From nifty_oc_historical
    spot=24500.0,               # Current Nifty price
    expiry_date=date(2026, 3, 6),  # Weekly expiry
    vix_current=14.5,
    vix_prev=14.2,              # Previous VIX (for velocity)
    pcr=0.95,                   # PE OI / CE OI
    prev_minute_greeks=None     # Optional: for velocity calc
)
```

### 2. Database Schema Updates

**New Columns Added to `nifty_oc_historical`:**

```sql
-- Metadata
timestamp DATETIME
dte INT (Days to Expiry)
charm DECIMAL(10, 6)

-- CE (Call) Greeks Metrics (17 columns)
ce_rank_label VARCHAR(20)         -- ATM/ITM/OTM/Deep_ITM/Scalp
ce_efficiency DECIMAL(10, 4)      -- Delta/|Theta| ratio
ce_vega_adj_efficiency DECIMAL(10, 4)
ce_charm_bleed_60m DECIMAL(10, 6) -- Delta loss in 60 min
ce_gamma_risk_score DECIMAL(10, 4)
ce_oi_change BIGINT
ce_delta_velocity DECIMAL(10, 6)  -- Delta change/min
ce_gamma_velocity DECIMAL(10, 6)
ce_theta_velocity DECIMAL(10, 6)
ce_iv_velocity DECIMAL(10, 6)
ce_alert_theta_trap TINYINT(1)
ce_alert_gamma_blast TINYINT(1)
ce_alert_negative_carry TINYINT(1)
ce_alert_lotto_flag TINYINT(1)

-- PE (Put) Greeks Metrics (17 columns)
pe_rank_label VARCHAR(20)
pe_efficiency DECIMAL(10, 4)
pe_vega_adj_efficiency DECIMAL(10, 4)
pe_charm_bleed_60m DECIMAL(10, 6)
pe_gamma_risk_score DECIMAL(10, 4)
pe_oi_change BIGINT
pe_delta_velocity DECIMAL(10, 6)
pe_gamma_velocity DECIMAL(10, 6)
pe_theta_velocity DECIMAL(10, 6)
pe_iv_velocity DECIMAL(10, 6)
pe_alert_theta_trap TINYINT(1)
pe_alert_gamma_blast TINYINT(1)
pe_alert_negative_carry TINYINT(1)
pe_alert_lotto_flag TINYINT(1)

-- Market-Level Metrics
net_delta_flow DECIMAL(10, 4)     -- CE Delta Sum - PE Delta Sum
market_bias VARCHAR(10)            -- BULLISH/BEARISH/NEUTRAL
vix_change_pct DECIMAL(10, 3)     -- VIX % change
```

**New Table: `User_` (Portfolio Tracking)**

```sql
CREATE TABLE User_ (
    trade_id INT AUTO_INCREMENT PRIMARY KEY,
    strike_price DECIMAL(10, 2),
    option_type ENUM('CE', 'PE'),
    quantity INT,
    entry_price DECIMAL(10, 2),
    entry_time DATETIME,
    exit_price DECIMAL(10, 2),
    exit_time DATETIME,
    status ENUM('OPEN', 'CLOSED'),
    pnl DECIMAL(15, 2),
    notes TEXT
);
```

**Re-run Schema Update:**
```bash
python apply_greeks_schema.py
```

### 3. Files Created

```
d:\Pycharm\Clone\IndexDataAnalyser\
├── core/
│   └── greeks_processor.py          ✅ Greeks calculation engine
├── docs/
│   ├── MARKET_HOLIDAYS.md            ✅ Market holiday guide
│   └── GREEKS_INTEGRATION.md         ✅ This file
├── setup_greeks_schema.sql           ✅ SQL schema update
└── apply_greeks_schema.py            ✅ Python schema applicator
```

## 📋 Remaining Tasks (Phase 2)

### 1. Integrate Greeks API Endpoints

Add these endpoints to `dashboard/api.py`:

**Required Endpoints:**
- `GET /api/greeks-pro` - Main Greeks data endpoint
- `GET /api/greeks/iv-rank` - IV rank calculation
- `GET /api/greeks/portfolio` - Portfolio net delta
- `GET /api/greeks/signals` - Entry/exit signals

### 2. Update Main.py Integration

Add Greeks processing to the main data collection loop:

```python
# In main.py, after option chain fetch
from core.greeks_processor import process_greeks_from_db
from datetime import date

# Get latest OC data from DB
with DatabaseManager.get_cursor() as cursor:
    cursor.execute("""
        SELECT * FROM nifty_oc_historical
        WHERE Date = CURDATE() AND Time = (SELECT MAX(Time) FROM nifty_oc_historical WHERE Date = CURDATE())
    """)
    db_rows = cursor.fetchall()

# Process Greeks
greeks_result = process_greeks_from_db(
    db_rows=db_rows,
    spot=spot_price,
    expiry_date=date(2026, 3, 6),  # Update weekly
    vix_current=vix_now,
    vix_prev=vix_prev,
    pcr=pcr,
    prev_minute_greeks=prev_greeks_snapshot
)

# Store greeks_result for API access
```

### 3. Create Greeks Dashboard HTML

Create `dashboard/greeks.html` with:
- Real-time Greeks metrics display
- Top 5 CE/PE strikes by efficiency
- Entry/Exit signal alerts
- Trend intensity gauge
- Portfolio net delta tracker
- Lotto strikes table (Scalp + Gamma Blast)

### 4. Add Config for Active Expiry

In `.env`, add:
```
ACTIVE_EXPIRY=2026-03-06
```

Update `core/config.py`:
```python
ACTIVE_EXPIRY: str = os.getenv("ACTIVE_EXPIRY", "2026-03-06")
```

**IMPORTANT**: Update `ACTIVE_EXPIRY` every Thursday evening after 3:30 PM to next week's expiry.

## 📊 How Greeks Processing Works

### Data Flow

```
1. main.py collects OC data → stores in nifty_oc_historical
2. main.py calls process_greeks_from_db()
3. Greeks processor reads latest DB rows
4. Calculates derived metrics (efficiency, velocity, alerts)
5. Returns processed data for API
6. dashboard/api.py serves /api/greeks-pro endpoint
7. greeks.html fetches and displays data
```

### Key Metrics Explained

**Efficiency Score** = `Delta / |Theta|`
- Shows profit potential vs time decay
- Higher = better risk/reward
- > 2.5 = Strong entry candidate

**Vega-Adjusted Efficiency** = `Delta / (|Theta| - Vega*VIX%Change)`
- Accounts for IV expansion/contraction
- More accurate during volatile periods

**Theta Trap**
- Detected when: `Hourly Theta / LTP > 15%`
- Means: Time decay is eating 15%+ of premium per hour
- Action: Exit immediately

**Gamma Blast**
- Detected when: `Gamma > 0.003`
- Means: Extreme price sensitivity
- Use: Scalping opportunities on expiry day

**Negative Carry**
- Detected when: `Gamma benefit < Theta cost`
- Means: Position is net bleeding value
- Action: Close or adjust

**Greeks Velocity**
- Tracks: Delta, Gamma, Theta, IV change per minute
- Use: Identify accelerating/decelerating positions
- Example: `delta_velocity = -0.005` means delta dropping fast

## 🎯 Trading Signals

### Entry Signals

**Bullish Entry (CE):**
- Efficiency ≥ 2.5
- Net Delta Flow > 0
- IV Rank < 60
- No Theta Trap

**Bearish Entry (PE):**
- Efficiency ≥ 2.5
- Net Delta Flow < 0
- IV Rank < 60
- No Theta Trap

### Exit Signals

- Efficiency < 1.0
- Theta Trap detected
- Delta Velocity < -0.005 (fading fast)

### Gamma Blast (Expiry Day)

- Gamma > 0.003
- Rank = "Scalp"
- Time: 1:30 PM - 2:30 PM window
- DTE = 0

## 🔧 Configuration

### Active Expiry Management

**Update Weekly** (Every Thursday 3:30 PM+):

1. Edit `.env`:
```
ACTIVE_EXPIRY=2026-03-13  # Next week's expiry
```

2. Restart applications:
```bash
# Stop current processes
# Ctrl+C on main.py and api.py

# Restart
python main.py
cd dashboard && python api.py
```

### Charm Handling

Charm is NOT always provided by Dhan API.

**In greeks_processor.py:**
```python
# Charm defaults to 0.0 if missing
charm = safe_float(row.get('charm', 0.0))
```

**No Black-Scholes calculation needed** - we simply use 0.0.

### Previous VIX Handling

On first run, `vix_prev = vix_current` (velocity = 0 is acceptable).

```python
# In main.py
vix_prev = vix_current if not prev_vix_stored else prev_vix_stored
```

## 📈 Portfolio Delta Tracking

### Adding Trades to User_ Table

```sql
-- Manual trade entry example
INSERT INTO User_ (strike_price, option_type, quantity, entry_price, notes)
VALUES (24500, 'CE', 50, 120.50, 'Bullish scalp on trend reversal');

-- Close trade
UPDATE User_
SET status = 'CLOSED', exit_price = 145.30, exit_time = NOW(),
    pnl = (145.30 - 120.50) * 50
WHERE trade_id = 1;
```

### Portfolio Net Delta Calculation

```
Net Delta = SUM(position_delta) for all OPEN trades

position_delta = quantity * current_delta

Example:
- Trade 1: 50 CE @ delta 0.45 = +22.5
- Trade 2: -25 PE @ delta -0.50 = +12.5
- Net Delta = +35.0 (NET LONG)
```

## 🔍 Testing

### Test Greeks Processing

```python
# test_greeks.py
from core.greeks_processor import process_greeks_from_db
from core.database import DatabaseManager
from datetime import date

with DatabaseManager.get_cursor() as cursor:
    cursor.execute("""
        SELECT * FROM nifty_oc_historical
        WHERE Date = '2026-03-03' LIMIT 10
    """)
    rows = cursor.fetchall()

result = process_greeks_from_db(
    db_rows=rows,
    spot=24500.0,
    expiry_date=date(2026, 3, 6),
    vix_current=14.5,
    vix_prev=14.2,
    pcr=0.95
)

print(f"Market Bias: {result['trend_intensity']['market_bias']}")
print(f"Net Delta Flow: {result['trend_intensity']['net_delta_flow']}")
print(f"Alerts: {len(result['alerts'])}")
print(f"CE Top Strike: {result['ce_ranked'][0]}")
```

### Verify Database Schema

```sql
-- Check Greeks columns exist
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'nifty_oc_historical'
  AND COLUMN_NAME LIKE '%efficiency%';

-- Check User_ table
DESCRIBE User_;

-- Verify data
SELECT strike_price, ce_efficiency, pe_efficiency, market_bias
FROM nifty_oc_historical
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
LIMIT 10;
```

## 🚨 Important Notes

### DO NOT:
- ❌ Calculate Greeks using Black-Scholes
- ❌ Re-calculate Delta, Theta, Gamma, Vega
- ❌ Assume Charm is always present in API
- ❌ Forget to update ACTIVE_EXPIRY weekly

### DO:
- ✅ Use Dhan's pre-calculated Greeks directly
- ✅ Default Charm to 0.0 if missing
- ✅ Update ACTIVE_EXPIRY every Thursday 3:30 PM+
- ✅ Handle prev_vix gracefully on first run
- ✅ Allow User_ table to be empty (no portfolio tracking initially)

## 📚 Next Steps

1. **Integrate API Endpoints** - Add Greeks endpoints to `dashboard/api.py`
2. **Update main.py** - Call Greeks processor in main loop
3. **Create Dashboard** - Build `dashboard/greeks.html`
4. **Test Integration** - Run full end-to-end test
5. **Deploy** - Update deployment scripts

## 🔗 References

- [Dhan API Documentation](https://dhanhq.co/docs/v2/)
- [Options Greeks Explained](https://www.investopedia.com/terms/g/greeks.asp)
- [PCR Analysis](https://www.investopedia.com/terms/p/putcallratio.asp)

---

**Last Updated**: March 3, 2026
**Status**: Phase 1 Complete (Database + Core Engine)
**Next**: Phase 2 (API + UI Integration)
