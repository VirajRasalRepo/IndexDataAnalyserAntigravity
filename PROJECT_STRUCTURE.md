# Index Data Analyser - Project Structure

## Directory Organization

```
IndexDataAnalyser/
├── dashboard/                    # Real-time OI Dashboard
│   ├── api.py                    # Flask REST API server (port 5000)
│   ├── index.html                # Main dashboard (OI Difference Live)
│   └── option_chain.html         # Option Chain view
│
├── core/                         # Core application logic
│   ├── __init__.py
│   ├── config.py                 # Configuration and environment variables
│   ├── database.py               # Database connection pool manager
│   ├── option_chain.py           # Option chain data fetching
│   ├── trade_sync.py             # Trade synchronization
│   ├── Utilities.py              # Utility functions
│   └── Constant.py               # Constants
│
├── streaming/                    # WebSocket implementation
│   ├── __init__.py
│   └── market_feed_websocket.py  # Real-time market feed via WebSocket
│
├── sql/                          # Database schemas
│   ├── OI_Data_Sql.sql           # Option chain historical table
│   ├── market_feed_realtime_SQL.sql  # Market feed real-time table
│   ├── schema_market_feed.sql    # Market feed schema
│   └── User_.sql                 # User table schema
│
├── docs/                         # Documentation
│   ├── OI_DASHBOARD_README.md    # Dashboard setup guide
│   ├── MIGRATION_GUIDE.md        # Migration instructions
│   └── WEBSOCKET_SETUP.md        # WebSocket setup guide
│
├── static/                       # Static files (if needed)
├── templates/                    # Flask templates (for web_app.py)
│
├── main.py                       # Main application entry point
├── setup_database.py             # Database setup script
├── web_app.py                    # Legacy Flask web app (port 5000)
├── .env                          # Environment variables (DO NOT COMMIT)
├── requirements.txt              # Python dependencies
└── README.md                     # Main project README

```

## File Purposes

### Dashboard Files
- **dashboard/api.py**: REST API server providing endpoints for dashboard data
  - `/api/health` - Health check
  - `/api/spot-price` - NIFTY spot price and VIX
  - `/api/option-chain` - Option chain data
  - `/api/expiry-dates` - Available expiry dates
  - `/api/oi-difference-live` - Time-series OI difference data

- **dashboard/index.html**: Main dashboard with OI Difference Live view
  - 3-minute interval time-series data
  - Fixed strike column with horizontal scrolling
  - VIX volatility calculations (15-min and 5-min expected moves)

- **dashboard/option_chain.html**: Traditional option chain view
  - Single timestamp OI, IV, LTP, Greeks display
  - Auto-refresh every 5 seconds

### Core Application Files
- **core/config.py**: Loads configuration from environment variables
- **core/database.py**: MySQL connection pool manager with context managers
- **core/option_chain.py**: Fetches option chain data from Dhan API
- **core/trade_sync.py**: Syncs trade data from Dhan to database
- **core/Utilities.py**: Helper functions for API calls
- **core/Constant.py**: Application constants

### WebSocket Files
- **streaming/market_feed_websocket.py**: Real-time market data streaming
  - Subscribes to NIFTY 50 and INDIA VIX
  - Stores tick data in `market_feed_realtime` table

### Main Application
- **main.py**: Entry point that orchestrates:
  1. Trade synchronization
  2. Option chain data fetching
  3. WebSocket market feed streaming

## Running the Application

### 1. Start Main Data Collection
```bash
python main.py
```
Runs continuously to collect:
- Trade data (every 30 seconds)
- Option chain data (every 1 minute during market hours)
- Real-time market feed via WebSocket

### 2. Start Dashboard API Server
```bash
cd dashboard
python api.py
```
Starts Flask server on `http://localhost:5000`

### 3. Open Dashboard
Navigate to:
- Main Dashboard: `dashboard/index.html`
- Option Chain: `dashboard/option_chain.html`

## Import Structure

### Root-level files
```python
# main.py
from core.config import Config
from core.database import DatabaseManager
from core.option_chain import OptionChainData
from core.trade_sync import TradeSync
from websocket.market_feed_websocket import DhanMarketFeed
```

### Core package files
```python
# core/option_chain.py
from .config import Config
from .database import DatabaseManager
from . import Utilities
```

### Dashboard API
```python
# dashboard/api.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import DatabaseManager
from core.config import Config
```

### WebSocket
```python
# streaming/market_feed_websocket.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Config
from core.database import DatabaseManager
```

## Database Tables

1. **nifty_oc_historical**: Option chain historical data
   - Strike price, OI, Volume, IV, Greeks (CE/PE)
   - Updated every 1 minute during market hours

2. **market_feed_realtime**: Real-time tick data
   - NIFTY 50 LTP, volume, OHLC
   - INDIA VIX LTP, volume, OHLC
   - Updated in real-time via WebSocket

3. **User_**: Trade data
   - Positions, orders, holdings

## Configuration

All configuration is managed through environment variables in `.env`:
```env
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=analyzer_db
LOG_LEVEL=INFO
DEBUG=True
```

## Notes

- The dashboard API runs on port 5000
- WebSocket connection auto-reconnects on failure
- Database uses connection pooling for efficiency
- All timestamps are in IST (Indian Standard Time)
- Market hours: 9:15 AM - 3:30 PM IST
