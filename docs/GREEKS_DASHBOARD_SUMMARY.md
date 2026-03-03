# Greeks Dashboard - Complete Summary

## 📊 Frontend (UI)

**File:** `dashboard/greeks.html` (1,820 lines)

### Components:
1. **Date/Time Selector**
   - Calendar picker with trading days only
   - Time grid (3-min intervals, market hours)
   - Auto-selects most recent date

2. **Metric Cards (6 cards, 2 rows)**
   - **Row 1:** Nifty Spot, India VIX, Net Delta Flow, IV Rank, DTE, PCR
   - **Row 2:** Put-Call Skew, Max Pain, ATM Straddle (NEW)

3. **Greeks Table (14 columns)**
   ```
   STRIKE | TYPE | LTP | IV | DELTA | GAMMA | VEGA | THETA |
   CHARM | γ-RISK | EFF | V-EFF | VEL | ALERTS
   ```
   - Shows top 10 CE + top 10 PE strikes
   - Color-coded values (green/red/yellow)
   - Hover tooltips for details

4. **Features**
   - Live refresh capability
   - Historical data viewer
   - PCR divergence alerts
   - Alert badges (⚠️⚡🩸🎰)
   - Velocity arrows (↑↓→)

---

## ⚙️ Backend (API)

**Files:**
- `dashboard/api.py` - REST endpoints
- `core/greeks_processor.py` - Greeks calculations (454 lines)

### Key Endpoints:

**`/api/greeks-pro` (Main Endpoint)**
- **Method:** GET
- **Params:** `date=YYYY-MM-DD`, `time=HH:MM:SS`
- **Returns:**
  ```json
  {
    "spot": 24000,
    "dte": 3,
    "vix": 15.2,
    "trend_intensity": {...},
    "pcr_divergence": {...},
    "put_call_skew": {...},      // NEW
    "max_pain": {...},            // NEW
    "straddle_premium": {...},    // NEW
    "ce_all": [...10 strikes],
    "pe_all": [...10 strikes],
    "iv_rank": 42.5
  }
  ```

**`/api/available-dates`**
- Returns: List of trading days with market hours data
- Filter: `TIME_TO_SEC(Time) >= 33300 AND <= 55800`
- Filter: `is_trading_day()` - excludes weekends/holidays

**`/api/available-times`**
- Returns: 3-minute interval timestamps for selected date
- Market hours: 9:15 AM - 3:30 PM IST

### Greeks Processor Functions:

**Core Calculations:**
```python
calc_efficiency(delta, theta)              # Delta/|Theta|
calc_vega_adjusted_efficiency(...)         # With IV expansion
calc_charm_bleed(charm)                    # Per hour: charm/6.5
calc_gamma_risk_score(gamma, dte)          # 0-10 scale
calc_greeks_velocity(current, prev)        # Rate of change + %
```

**New Analytics:**
```python
calc_put_call_skew(atm_ce_iv, atm_pe_iv)  # Fear/Euphoria
calc_max_pain(strikes_data)                # MM target strike
calc_straddle_premium(ce, pe, spot)        # Expected move
```

**Alerts:**
```python
calc_theta_trap(theta, ltp)                # >15% hourly decay
calc_gamma_blast(gamma)                    # >0.003
calc_negative_carry(gamma, theta)          # Gamma < Theta benefit
```

**Trend Analysis:**
```python
calc_trend_intensity(ce, pe)               # Top 5 delta sum
check_pcr_delta_divergence(pcr, delta)     # Extreme thresholds
```

---

## 🗄️ Database Schema

**Table:** `nifty_oc_historical`

### Greeks Columns (28 total):

**Basic Greeks (from Dhan API):**
```sql
ce_delta          DECIMAL(10,4)   -- Rate of price change
ce_gamma          DECIMAL(10,4)   -- Rate of delta change
ce_theta          DECIMAL(10,4)   -- Time decay per day
ce_vega           DECIMAL(10,4)   -- IV sensitivity
charm             DECIMAL(10,6)   -- Delta decay over time

pe_delta, pe_gamma, pe_theta, pe_vega  -- Same for puts
```

**Derived Metrics (calculated by processor):**
```sql
ce_efficiency              DECIMAL(10,4)   -- Delta/|Theta|
ce_vega_adj_efficiency     DECIMAL(10,4)   -- IV-adjusted
ce_charm_bleed_60m         DECIMAL(10,6)   -- Per hour rate
ce_gamma_risk_score        DECIMAL(10,4)   -- 0-10 scale

pe_efficiency, pe_vega_adj_efficiency, etc.
```

**Velocity Metrics:**
```sql
ce_delta_velocity          DECIMAL(10,6)   -- Absolute change
ce_gamma_velocity          DECIMAL(10,6)
ce_theta_velocity          DECIMAL(10,6)

pe_delta_velocity, pe_gamma_velocity, etc.
```

**Alert Flags:**
```sql
ce_alert_theta_trap        TINYINT(1)      -- Boolean
ce_alert_gamma_blast       TINYINT(1)

pe_alert_theta_trap, pe_alert_gamma_blast
```

**Aggregate:**
```sql
net_delta_flow             DECIMAL(10,4)   -- CE - PE delta sum
```

### Data Stats:
- **Total Records:** 168,423 strikes
- **Date Range:** 2026-02-25 to 2026-03-02
- **Dates with Data:** 5 trading days
- **Records with Delta:** 168,423 (100%)
- **Records with Efficiency:** 158,791 (94%)

---

## 🎨 Design File (.pen)

**File:** `Designs/GreeksDashboard.pen`

### Purpose:
- UI mockup and design specification
- Created using Pencil design tool
- Visual reference for dashboard layout

### Contents:
- Metric card layouts
- Table column arrangement
- Color scheme definitions
- Typography specifications
- Responsive breakpoints

**Note:** .pen files are encrypted binary format, readable only by Pencil MCP tool.

---

## 📁 Supporting Files

### Scripts:
```
backfill_greeks_historical.py  - Populate historical Greeks data
apply_greeks_schema.py         - Add Greeks columns to DB
setup_greeks_schema.sql        - SQL schema definitions
check_greeks_data.py           - Verify data integrity
test_greeks_api.py             - API endpoint tests
```

### Documentation:
```
docs/GREEKS_INTEGRATION.md     - Setup guide
docs/GREEKS_STARTUP_GUIDE.md   - Quick start
docs/GREEKS_TESTING_SUMMARY.md - Test results
docs/GREEKS_FORMULA_FIXES.md   - Formula corrections
docs/UI_ENHANCEMENTS.md        - UI changes log
```

---

## 🔄 Data Flow

```
1. User Opens Dashboard
   └─> greeks.html loads

2. Date/Time Selection
   └─> /api/available-dates fetches trading days
   └─> /api/available-times fetches timestamps

3. Greeks Data Request
   └─> /api/greeks-pro?date=2026-03-02&time=10:36:00
       ├─> Query DB for raw OI/IV/LTP data
       ├─> greeks_processor.py calculates:
       │   ├─> Efficiency, Charm Bleed, Gamma Risk
       │   ├─> Vega-Adj Efficiency, Velocities
       │   ├─> Put-Call Skew, Max Pain, Straddle
       │   └─> Alert flags, Trend intensity
       └─> Return JSON with all metrics

4. UI Rendering
   ├─> Update 6 metric cards
   ├─> Render 14-column table
   ├─> Color-code values
   └─> Show alert badges
```

---

## 🎯 Key Features

### Analytics:
✅ 8 Core Greeks (Delta, Gamma, Theta, Vega, Charm, etc.)
✅ 5 Derived Metrics (Efficiency, Vega-Adj, Gamma Risk, etc.)
✅ 3 Advanced Analytics (Skew, Max Pain, Straddle)
✅ 4 Alert Types (Theta Trap, Gamma Blast, Bleed, Lotto)
✅ 2 Trend Indicators (Delta Flow, PCR Divergence)

### Formulas Fixed:
✅ Charm Bleed: charm/6.5 (per hour, not per minute)
✅ Gamma Risk: 0-10 scale (normalized, not huge numbers)
✅ PCR Thresholds: 0.70/1.50 (realistic, not 0.80/1.30)
✅ Vega-Adj Eff: Clamped, VIX direction aware
✅ Velocity: Absolute + relative % with direction

### Data Coverage:
- **168,423 strikes** across 5 trading days
- **94% Greeks coverage** (efficiency calculated)
- **Market hours only** (9:15 AM - 3:30 PM)
- **Trading days only** (excludes weekends/holidays)

---

## 📊 Technical Stack

**Frontend:**
- Vanilla JavaScript (no frameworks)
- HTML5 + CSS3
- Fetch API for async requests
- 1,820 lines of code

**Backend:**
- Flask REST API (Python)
- MySQL database
- Dhan API integration (Greeks source)
- 454 lines Greeks processor

**Database:**
- MySQL 8.0
- 28 Greeks columns
- Indexed by Date, Time, Strike_price
- 168k+ records

---

## 🚀 Quick Start

```bash
# 1. Start Flask Server
python main.py

# 2. Open Dashboard
http://localhost:5000/greeks.html

# 3. Select Date/Time
Click calendar → Pick 2026-03-02 → Select 10:36:00

# 4. View Greeks
Table shows 20 strikes (10 CE + 10 PE) with all metrics
```

---

## 📈 Performance

- **API Response:** ~500ms (DB query + calculations)
- **UI Render:** ~100ms (20 strikes table)
- **Backfill Speed:** ~0.17 sec/timestamp (168k in 45 mins)
- **Data Size:** ~50 MB for 5 days

---

**Created:** 2026-03-03
**Version:** 1.0
**Status:** Production ✅
