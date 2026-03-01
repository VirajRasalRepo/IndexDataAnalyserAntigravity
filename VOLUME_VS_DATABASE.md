# Volume: Database vs Dashboard

## How Volume is Stored in Database

### Database Table: `nifty_oc_historical`

**Columns:**
- `ce_volume` - Call option volume (raw number)
- `pe_volume` - Put option volume (raw number)

**Example Raw Data:**
```sql
Strike_price | Time     | ce_volume | pe_volume
25400.0      | 09:15:00 | 1234000   | 95768530
25400.0      | 09:18:00 | 1468000   | 96120000
25400.0      | 09:21:00 | 1702000   | 96480000
```

### What These Numbers Mean:

| Timestamp | CE Volume | PE Volume |
|-----------|-----------|-----------|
| 09:15:00  | 1,234,000 | 95,768,530 |
| 09:18:00  | 1,468,000 | 96,120,000 |
| 09:21:00  | 1,702,000 | 96,480,000 |

**Important:** These are **cumulative** volumes since market open (9:15 AM)

---

## How Volume is Calculated for Dashboard

### Step 1: Fetch from Database (API does this)

API queries the database and gets raw volume numbers:
```python
# Line 326-327 in dashboard/api.py
h1.ce_volume,  # Gets raw value: 1234000
h1.pe_volume   # Gets raw value: 95768530
```

### Step 2: Calculate Volume Difference

API calculates the **change** between timestamps:
```python
# Line 375-377 in dashboard/api.py
curr_data[strike]['ce_vol_diff'] = curr_data[strike]['ce_vol'] - prev_data[strike]['ce_vol']
curr_data[strike]['pe_vol_diff'] = curr_data[strike]['pe_vol'] - prev_data[strike]['pe_vol']
```

**Example Calculation:**
```
Timestamp: 09:18:00
CE Vol: 1,468,000
Previous (09:15:00) CE Vol: 1,234,000

CE Vol Diff = 1,468,000 - 1,234,000 = 234,000 contracts
```

### Step 3: Display on Dashboard (with formatting)

Dashboard JavaScript divides by 1000 for readability:
```javascript
// Line 757-758 in dashboard/index.html
const ceVol = (strikeData.ce_vol / 1000 || 0).toFixed(0);      // 1234000 / 1000 = 1234
const ceVolDiff = (strikeData.ce_vol_diff / 1000 || 0).toFixed(0);  // 234000 / 1000 = 234
```

---

## Complete Flow Example

### Database → API → Dashboard

**Strike 25400 CE at 09:18:00:**

| Stage | CE Volume | CE Vol Diff | Display |
|-------|-----------|-------------|---------|
| **Database** | 1,468,000 | (not stored) | - |
| **API Calculation** | 1,468,000 | 234,000 | (JSON) |
| **Dashboard Display** | 1468K | +234K | ✅ Shown to user |

---

## Key Differences Summary

### 1. Volume (ce_vol / pe_vol)

**Database:**
```
ce_volume = 1,234,000 (raw cumulative count)
```

**Dashboard:**
```
Vol(K): 1234K (÷ 1000 for readability)
```

### 2. Volume Difference (ce_vol_diff / pe_vol_diff)

**Database:**
```
NOT stored - calculated by API on the fly
```

**API Calculation:**
```python
ce_vol_diff = current_volume - previous_volume
            = 1,468,000 - 1,234,000
            = 234,000
```

**Dashboard:**
```
ΔVol(K): +234K (÷ 1000 for readability)
```

---

## Why Volume is Cumulative in Database

### Example Timeline (Strike 25400 CE):

| Time     | Trades | Total Volume (DB) | Display |
|----------|--------|-------------------|---------|
| 09:15:00 | 1,234,000 contracts traded | 1,234,000 | 1234K |
| 09:18:00 | 234,000 more contracts traded | 1,468,000 | 1468K |
| 09:21:00 | 234,000 more contracts traded | 1,702,000 | 1702K |

**Volume in DB = Total contracts traded since market open**

### But Dashboard Shows:

| Time     | Vol(K) | ΔVol(K) |
|----------|--------|---------|
| 09:15:00 | 1234K  | +1234K  |
| 09:18:00 | 1468K  | +234K   |
| 09:21:00 | 1702K  | +234K   |

**ΔVol(K) = New contracts traded in last 3 minutes**

---

## Important Notes

### 1. Database Stores Cumulative Volume

The `ce_volume` and `pe_volume` columns store the **total cumulative volume** for the day, not the difference.

**Why?** Because Dhan API provides cumulative volume, and we store exactly what we receive.

### 2. API Calculates Differences

The API compares consecutive 3-minute intervals to calculate how many new contracts were traded:

```python
new_trades = current_interval_volume - previous_interval_volume
```

### 3. Dashboard Formats for Display

Dashboard divides by 1000 to show "K" (thousands) for easier reading:
- `1,234,000` → `1234K`
- `234,000` → `234K`

---

## Real Example from Your Dashboard

Looking at your screenshot:

**Strike 25300 CE at 09:15:00:**
- **Vol(K): 309** = Database has `ce_volume = 309,000`
- **ΔVol(K): +309** = 309,000 contracts traded in last 3 minutes (since market just opened)

**Why Vol = ΔVol at 09:15?**
Because it's the first timestamp! All trading happened in this interval, so:
- Previous volume = 0 (market just opened)
- Current volume = 309,000
- Difference = 309,000 - 0 = 309,000

---

## Quick Reference

| What You See | What It Means | Where It Comes From |
|-------------|---------------|---------------------|
| **Vol(K): 1234** | 1,234,000 total contracts traded today | Database: `ce_volume` ÷ 1000 |
| **ΔVol(K): +234** | 234,000 new contracts in last 3 min | API calculation: current - previous ÷ 1000 |

---

## Summary

1. **Database**: Stores raw cumulative volume (e.g., 1,234,000)
2. **API**: Calculates differences between intervals (e.g., 234,000)
3. **Dashboard**: Divides by 1000 and shows as "K" (e.g., 1234K, +234K)

The volume in the dashboard is **derived from** the database but **formatted for readability**!
