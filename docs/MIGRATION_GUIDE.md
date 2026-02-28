# Migration Guide: Old to New Code

## Quick Start

### Step 1: Create `.env` file

Copy your credentials from the old `main.py`:

```bash
# Create .env from template
copy .env.example .env
```

Edit `.env` and add your actual credentials:

```env
DHAN_CLIENT_ID=1107702034
DHAN_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9...
DB_PASSWORD=qwerty123456
```

### Step 2: Install new dependency

```bash
pip install python-dotenv
```

### Step 3: Run the refactored code

```bash
python main.py
```

## What Changed?

### File Structure

**Before:**
```
- main.py (everything in one file)
- Utilities.py
```

**After:**
```
- main.py (clean orchestration)
- config.py (configuration management)
- database.py (DB connection handling)
- trade_sync.py (trade synchronization)
- option_chain.py (option chain logic)
- Utilities.py (unchanged)
- .env (your credentials - git-ignored)
- .env.example (template for others)
```

### Key Changes

#### 1. **Credentials Now in .env File**

**Old Code:**
```python
CLIENT_ID = "1107702034"
ACCESS_TOKEN = "eyJ0eXA..."
DB_CONFIG = {"password": "qwerty123456"}
```

**New Code:**
```python
# In .env file (not committed to git)
DHAN_CLIENT_ID=1107702034
DHAN_ACCESS_TOKEN=eyJ0eXA...
DB_PASSWORD=qwerty123456
```

#### 2. **Database Connections**

**Old Code:**
```python
# New connection every 4 seconds
db_connection = mysql.connector.connect(**DB_CONFIG)
cursor = db_connection.cursor()
# ... do work ...
cursor.close()
db_connection.close()
```

**New Code:**
```python
# Connection pooling (much more efficient)
DatabaseManager.initialize_pool(pool_size=5)

# Context manager auto-handles connection
with DatabaseManager.get_cursor() as cursor:
    cursor.execute(query)
    # Auto-commit and cleanup
```

#### 3. **Logging**

**Old Code:**
```python
print(f"[{now.strftime('%H:%M:%S')}] Synced {count} trades")
print(f"Trade Sync Error: {e}")
```

**New Code:**
```python
logger.info(f"Synced {count} new trades")
logger.error(f"Trade sync failed: {e}", exc_info=True)
```

#### 4. **Market Hours Check**

**Old Code:**
```python
if True:  # Market Hours Check (never actually checked!)
    # ... fetch data ...
```

**New Code:**
```python
if not is_market_hours():
    logger.info("Outside market hours. Waiting...")
    time.sleep(60)
    continue
```

#### 5. **Error Handling**

**Old Code:**
```python
except Exception as e:
    print(f"Error: {e}")
    return 0  # Silent failure
```

**New Code:**
```python
except TradeSyncError as e:
    logger.error(f"Trade sync failed: {e}")
    # Specific error types, proper logging
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise  # Don't hide unexpected errors
```

#### 6. **Code Organization**

**Old Code:**
```python
# 179 lines, everything mixed together
# Functions, database code, API calls all in one file
```

**New Code:**
```python
# main.py: 128 lines (clean orchestration)
# config.py: Configuration management
# database.py: DB operations
# trade_sync.py: Trade logic
# option_chain.py: OI data logic
```

## Behavior Differences

### What Works Exactly the Same:
- ✅ Trade synchronization logic
- ✅ Option chain data fetching
- ✅ Database table structure
- ✅ Data format and storage
- ✅ Timing intervals (60s for trades, 4s for OI)

### What's Different (Better):
- ✅ **Market hours are now checked** (was `if True:` before)
- ✅ **Credentials are secure** (not in git)
- ✅ **Database connections are pooled** (better performance)
- ✅ **Batch inserts** instead of one-by-one (faster)
- ✅ **Proper logging** with levels and timestamps
- ✅ **Better error messages** for debugging

## Backwards Compatibility

### Database Tables
No changes required! The new code uses the same:
- `USER_TRADES` table structure
- `NIFTY_OC_HISTORICAL` table structure

### Data Format
All data is stored in exactly the same format, so your existing queries and analysis code will work without changes.

## Testing the Migration

### 1. Test with dry run
You can temporarily disable market hours check for testing:

```python
# In main.py, modify is_market_hours()
def is_market_hours() -> bool:
    return True  # Always return True for testing
```

### 2. Compare outputs
Run both versions side by side and compare:
- Trade counts should match
- Strike prices stored should match
- Database rows should be identical

### 3. Check logs
New code provides much better visibility:
```
2026-02-24 10:15:30 - __main__ - INFO - Index Data Analyser Started
2026-02-24 10:15:31 - __main__ - INFO - Using expiry date: 2026-02-27
2026-02-24 10:15:32 - trade_sync - INFO - Successfully synced 5 new trades
2026-02-24 10:15:33 - __main__ - INFO - Iteration 1: Stored 31 strikes (Spot: 23450.75)
```

## Rollback Plan

If you need to rollback to the old code:

```bash
# The old code is still in git history
git checkout HEAD~1 main.py
```

Or keep a backup:
```bash
copy main.py main_old.py  # Before migration
```

## Need Help?

### Common Issues

**Issue: `ModuleNotFoundError: No module named 'dotenv'`**
```bash
pip install python-dotenv
```

**Issue: `ConfigurationError: Missing required configuration`**
- Check that `.env` file exists
- Verify all required variables are set

**Issue: `RuntimeError: Connection pool not initialized`**
- Make sure `DatabaseManager.initialize_pool()` is called before use
- This is handled automatically in `initialize_application()`

### Questions?
Open an issue or check [README.md](README.md) for detailed documentation.
