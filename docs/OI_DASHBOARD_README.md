# OI Data Dashboard - Setup Guide

A professional real-time Option Chain (OI) data dashboard with live updates from your database.

## Features

✅ **Real-time Data**: Auto-refreshes every 5 seconds
✅ **Professional Design**: Dark theme dashboard from OiDataDashboard.pen
✅ **Live OI Analysis**: Displays Call/Put OI, IV, Greeks, and signals
✅ **Spot Price Indicator**: Highlights ATM strike in the table
✅ **Filter Controls**: Filter by symbol, expiry, and strike step
✅ **Responsive Layout**: Modern, clean interface

---

## Quick Start

### 1. Install Dependencies

```bash
pip install flask flask-cors
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

### 2. Start the Backend API Server

Open a **terminal** and run:

```bash
python oi_dashboard_api.py
```

You should see:

```
Starting OI Dashboard API server...
 * Running on http://0.0.0.0:5000
```

Keep this terminal window **open** and running.

### 3. Open the Dashboard

Open [static/oi_dashboard.html](static/oi_dashboard.html) in your web browser:

**Option A: Direct File Open**
- Navigate to: `d:\Pycharm\Clone\IndexDataAnalyser\static\oi_dashboard.html`
- Double-click to open in your default browser

**Option B: Command Line**
```bash
start static/oi_dashboard.html
```

---

## Dashboard Overview

### Layout

```
┌─────────────┬────────────────────────────────────────────────┐
│             │  NIFTY 50: 22,040.50 (+0.5%)                   │
│  SIDEBAR    │  INDIA VIX: 15.34 (-2.1%)                      │
│             ├────────────────────────────────────────────────┤
│ - Dashboard │  [Symbol] [Expiry] [Strike Step] [Apply] [Reset]
│ - Option    ├────────────────────────────────────────────────┤
│   Chain     │                                                │
│ - OI Multi  │   CALLS (CE)  │  STRIKE  │  PUTS (PE)          │
│   Strike    │  ────────────────────────────────────────────  │
│ - Greeks    │  Signal | OI | IV | LTP  │  LTP | OI | Signal │
│             │   ...option chain data...                      │
│             │  ────────────────────────────────────────────  │
│  Reports    │  Last updated: 2026-02-26 00:20:15 ●           │
│ - Historical│                                                │
│ - Signals   │                                                │
└─────────────┴────────────────────────────────────────────────┘
```

### Features Explanation

1. **Stats Cards**
   - NIFTY 50: Shows current spot price and percentage change
   - INDIA VIX: Shows volatility index

2. **Filter Controls**
   - **Symbol**: Select instrument (currently NIFTY)
   - **Expiry Date**: Choose option expiry
   - **Strike Step**: Filter strikes (50/100/200 point steps)
   - **Apply Filters**: Fetch data with selected filters
   - **Reset**: Clear all filters

3. **Option Chain Table**
   - **CALLS (CE)**: Call option data on the left
   - **STRIKE**: Strike prices in center (highlighted for ATM)
   - **PUTS (PE)**: Put option data on the right
   - **Columns**:
     - Signal: BULLISH/BEARISH/NEUTRAL indicators
     - OI (Lakhs): Open Interest in lakhs
     - Chng OI: Change in OI (green = increase, red = decrease)
     - IV: Implied Volatility (%)
     - LTP: Last Traded Price
     - Delta: Option Delta value

4. **Auto-Refresh**
   - Dashboard refreshes every 5 seconds automatically
   - Green pulsing indicator shows active refresh

---

## API Endpoints

The backend provides these REST endpoints:

### 1. Health Check
```
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-26T00:20:15.123456"
}
```

### 2. Spot Price & VIX
```
GET /api/spot-price
```

**Response:**
```json
{
  "nifty": {
    "value": 22040.50,
    "change_pct": 0.5,
    "timestamp": "2026-02-26 00:20:15"
  },
  "vix": {
    "value": 15.34,
    "change_pct": -2.1
  }
}
```

### 3. Option Chain Data
```
GET /api/option-chain?symbol=NIFTY&expiry=2026-03-02&strike_step=50
```

**Response:**
```json
{
  "spot_price": 22040.50,
  "timestamp": "2026-02-26 00:20:15",
  "data": [
    {
      "strike": 22000,
      "ce": {
        "signal": "BULLISH",
        "oi": 45.32,
        "oi_change": 2.5,
        "iv": 15.25,
        "ltp": 120.50,
        "delta": 0.52
      },
      "pe": {
        "signal": "BEARISH",
        "oi": 38.15,
        "oi_change": -1.2,
        "iv": 14.85,
        "ltp": 95.25,
        "delta": -0.48
      },
      "is_atm": true
    }
    // ... more strikes
  ]
}
```

### 4. Expiry Dates
```
GET /api/expiry-dates
```

**Response:**
```json
[
  "2026-03-02",
  "2026-03-10",
  "2026-03-17",
  "2026-03-24",
  "2026-03-30"
]
```

---

## Database Schema

The dashboard reads from the `nifty_oc_historical` table:

```sql
SELECT
    Strike_price,
    Spot_price,
    ce_oi, ce_IV, ce_delta, ce_price, ce_signal,
    pe_oi, pe_IV, pe_delta, pe_price, pe_signal,
    Date, Time
FROM nifty_oc_historical
ORDER BY Date DESC, Time DESC, Strike_price ASC
```

---

## Customization

### Change Auto-Refresh Interval

Edit [static/oi_dashboard.html](static/oi_dashboard.html), line ~750:

```javascript
// Change from 5000ms (5 seconds) to desired interval
refreshInterval = setInterval(fetchData, 5000);
```

### Change API URL

If running the API on a different port or host, update line ~721:

```javascript
const API_BASE = 'http://localhost:5000/api';
```

### Add More Instruments

Edit [oi_dashboard_api.py](oi_dashboard_api.py) and update the `/api/option-chain` endpoint to support more symbols.

---

## Troubleshooting

### Issue: "Failed to fetch data"

**Solution:**
1. Ensure the API server is running (`python oi_dashboard_api.py`)
2. Check console (F12) for CORS errors
3. Verify database connection in terminal logs

### Issue: "No data available"

**Solution:**
1. Run `python main.py` to populate the database with live data
2. Check that `nifty_oc_historical` table has recent data:
   ```sql
   SELECT COUNT(*) FROM nifty_oc_historical;
   ```

### Issue: Table shows "Loading..." forever

**Solution:**
1. Open browser console (F12)
2. Check for JavaScript errors
3. Verify API endpoint is accessible: http://localhost:5000/api/health

### Issue: CORS errors in browser

**Solution:**
```bash
pip install flask-cors
```

Then restart the API server.

---

## Color Scheme

The dashboard uses a professional dark theme:

- **Primary Blue**: `#135bec` (Buttons, active states)
- **Green (Positive)**: `#10b981` (Gains, bullish signals)
- **Red (Negative)**: `#f43f5e` (Losses, bearish signals)
- **Background**: `#101622` (Main dark navy)
- **Cards**: `#1e293b` (Lighter gray)

---

## Next Steps

1. ✅ **Populate Database**: Run `python main.py` to collect live data
2. ✅ **Start API Server**: Run `python oi_dashboard_api.py`
3. ✅ **Open Dashboard**: Open `static/oi_dashboard.html` in browser
4. 🔄 **Watch Live Updates**: Data refreshes automatically every 5 seconds

---

## Support

For issues or questions:
- Check [main README.md](README.md) for database setup
- Review API logs in terminal where `oi_dashboard_api.py` is running
- Check browser console (F12) for frontend errors

---

🚀 **Enjoy your professional OI Data Dashboard!**
