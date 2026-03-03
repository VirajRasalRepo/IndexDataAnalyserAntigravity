# Market Holidays Configuration

## Overview

The Index Data Analyser now includes comprehensive market holiday support for the Indian stock market (NSE/BSE). The system automatically skips weekends (Saturday/Sunday) and market holidays when:

- Calculating next market open time
- Scheduling data fetching
- Validating trading days in the API
- Performing post-market trade synchronization

## Features

✅ **Weekend Detection**: Automatically skips Saturdays and Sundays
✅ **Holiday Calendar**: Pre-configured with Indian stock market holidays for 2025-2027
✅ **Smart Scheduling**: Calculates exact next trading day, skipping holidays
✅ **API Validation**: Frontend date pickers auto-adjust to skip non-trading days
✅ **Post-Market Sync**: Only performs trade sync on actual trading days

## Holiday Calendar Location

The market holidays are defined in:

**File**: [`core/config.py`](../core/config.py)
**Variable**: `Config.MARKET_HOLIDAYS`

```python
MARKET_HOLIDAYS = [
    "2026-01-26",  # Republic Day
    "2026-03-03",  # Holi
    # ... more holidays ...
]
```

## How It Works

### 1. Trading Day Validation

The `is_trading_day()` function checks:
1. If the date is a weekend (returns `False`)
2. If the date is in the `MARKET_HOLIDAYS` list (returns `False`)
3. Otherwise returns `True`

```python
# Example usage in main.py
if is_trading_day(datetime.now()):
    # Perform trading day operations
    sync_trades()
```

### 2. Smart Market Scheduling

The `get_next_market_open_time()` function:
1. Checks if market opens later today (if it's a trading day)
2. Otherwise, finds the next trading day by skipping weekends and holidays
3. Returns the exact datetime for market open (9:15 AM IST)

```python
# Example log output
next_open = get_next_market_open_time()
# Output: "Market closed. Next market open: 2026-03-04 09:15:00"
# (Skips March 3rd - Holi holiday)
```

### 3. API Endpoint Validation

The API endpoint `/api/is-trading-day` now returns:

```json
{
  "date": "2026-03-03",
  "is_trading_day": false,
  "reason": "Market Holiday: Holi",
  "next_trading_day": "2026-03-04"
}
```

### 4. Frontend Date Picker

The dashboard's date picker automatically:
- Disables holiday dates in the calendar
- Shows visual indicators for holidays
- Auto-adjusts to previous/next trading day when a holiday is selected

## Updating the Holiday Calendar

### Annual Update Required

The holiday calendar should be updated **annually** when the NSE/BSE releases the official trading calendar.

### Steps to Update

1. **Get Official Calendar**: Visit [NSE India - Trading Calendar](https://www.nseindia.com/regulations/trading-holidays)

2. **Open Config File**: Edit [`core/config.py`](../core/config.py)

3. **Add New Year's Holidays**: Add holidays in `YYYY-MM-DD` format:

```python
# 2027 Holidays (example)
"2027-01-26",  # Republic Day
"2027-03-10",  # Id-Ul-Fitr
"2027-03-25",  # Holi
# ... add all holidays ...
```

4. **Format**: Always use `YYYY-MM-DD` format (ISO 8601)

5. **Comments**: Add holiday name as comment for clarity

6. **Test**: Restart the application to verify:

```bash
python main.py
```

### Where to Find Official Holidays

- **NSE**: https://www.nseindia.com/regulations/trading-holidays
- **BSE**: https://www.bseindia.com/markets/MarketInfo/DispNewNoticesCirculars.aspx
- **Moneycontrol**: https://www.moneycontrol.com/markets/trading-holiday/

## Current Holidays Included

### 2026 Holidays (13 holidays)

| Date | Holiday |
|------|---------|
| 2026-01-26 | Republic Day |
| 2026-03-03 | Holi |
| 2026-03-20 | Id-Ul-Fitr (Ramadan Eid) |
| 2026-03-30 | Mahavir Jayanti |
| 2026-04-03 | Good Friday |
| 2026-04-06 | Shri Ram Navami |
| 2026-04-14 | Dr. Baba Saheb Ambedkar Jayanti |
| 2026-05-01 | Maharashtra Day |
| 2026-05-27 | Id-Ul-Adha (Bakri Eid) |
| 2026-06-16 | Muharram |
| 2026-08-15 | Independence Day |
| 2026-09-16 | Ganesh Chaturthi |
| 2026-10-02 | Mahatma Gandhi Jayanti |
| 2026-10-10 | Dussehra |
| 2026-10-25 | Diwali (Laxmi Pujan) |
| 2026-10-26 | Diwali (Balipratipada) |
| 2026-11-13 | Guru Nanak Jayanti |
| 2026-12-25 | Christmas |

> **Note**: Some holidays (especially Islamic festivals) are based on lunar calendar and may shift by ±1 day. Always verify with official NSE calendar closer to the date.

## Testing Holiday Detection

### Test if a Date is a Trading Day

Run this in Python console:

```python
from datetime import datetime
from core.config import Config

# Test a known holiday
test_date = datetime(2026, 3, 3)  # Holi
date_str = test_date.strftime('%Y-%m-%d')

if date_str in Config.MARKET_HOLIDAYS:
    print(f"{date_str} is a market holiday")
else:
    print(f"{date_str} is a trading day")
```

### Test Next Market Open Calculation

```python
from main import get_next_market_open_time

# On March 2, 2026 (Tuesday before Holi on March 3)
next_open = get_next_market_open_time()
print(f"Next market open: {next_open}")
# Expected: 2026-03-04 09:15:00 (skips Holi)
```

### Test API Endpoint

```bash
curl "http://localhost:5000/api/is-trading-day?date=2026-03-03"
```

Expected response:
```json
{
  "date": "2026-03-03",
  "is_trading_day": false,
  "message": "Market is closed (holiday or weekend)"
}
```

## Logs and Monitoring

### Market Closed - Holiday

When the market is closed due to a holiday, you'll see logs like:

```
2026-03-03 10:00:00 - __main__ - INFO - Market closed. Next market open: 2026-03-04 09:15:00
2026-03-03 10:00:00 - __main__ - INFO - Sleeping until 08:45:00 (1365 minutes)
```

### Market Closed - Weekend

```
2026-03-01 10:00:00 - __main__ - INFO - Market closed. Next market open: 2026-03-03 09:15:00
2026-03-01 10:00:00 - __main__ - INFO - Sleeping until 08:45:00 (2835 minutes)
```

### Post-Market Sync Skipped (Holiday)

If a holiday falls on a weekday, post-market sync is skipped:

```
2026-03-03 15:35:00 - __main__ - INFO - Market closed. Next market open: 2026-03-04 09:15:00
# No "Performing final trade sync" message on holidays
```

## Special Handling

### Muhurat Trading (Diwali)

Some years have special **Muhurat Trading** sessions during Diwali evening. These are typically 1-hour sessions and are **NOT** included as full trading days in the current implementation.

If you need to handle Muhurat trading:
1. Remove Diwali from `MARKET_HOLIDAYS`
2. Add special time handling in `is_market_hours()` for that specific date

### Emergency Trading Halts

In case of emergency market closures (cyclones, national emergencies):
1. Quickly add the date to `MARKET_HOLIDAYS` in `config.py`
2. Restart the application: `python main.py`
3. The system will automatically adjust schedules

## Troubleshooting

### Issue: Application Still Fetches Data on Holiday

**Solution**:
1. Verify the date is in `Config.MARKET_HOLIDAYS`
2. Restart the application (config is loaded on startup)
3. Check logs for "Next market open" message

### Issue: Holiday Not Recognized

**Solution**:
1. Check date format is `YYYY-MM-DD` (not `DD-MM-YYYY`)
2. Verify no extra spaces or special characters
3. Ensure Config.py is saved properly

### Issue: Wrong Holiday Dates (Lunar Calendar Holidays)

**Solution**:
1. Islamic holidays (Eid, Muharram) depend on moon sighting
2. Update dates when NSE announces official calendar (usually 1-2 months before)
3. Set reminders to check NSE website in:
   - January (for full year calendar)
   - 1 month before each lunar holiday

## Future Enhancements

Potential improvements for holiday management:

1. **Auto-Update from NSE API**: Fetch holidays automatically from NSE API
2. **Holiday Database Table**: Store holidays in MySQL for runtime updates
3. **UI Holiday Manager**: Web interface to add/remove holidays
4. **Holiday Categories**: Differentiate between full/half-day trading holidays
5. **Multi-Year Bulk Import**: Import holidays from CSV/JSON files

## References

- [NSE Trading Holidays](https://www.nseindia.com/regulations/trading-holidays)
- [BSE Trading Holidays](https://www.bseindia.com/markets/MarketInfo/DispNewNoticesCirculars.aspx)
- [SEBI Guidelines on Trading Holidays](https://www.sebi.gov.in/)

---

**Last Updated**: March 2, 2026
**Next Review**: January 2027 (for 2027 holidays)
