# Index Data Analyser

A professional Python application for real-time NIFTY option chain analysis with an interactive web dashboard.

## Features

- **📊 Real-time OI Dashboard**: Professional web interface with live data updates
- **📈 Option Chain Analysis**: Comprehensive OI, IV, Greeks, and signals tracking
- **⚡ WebSocket Streaming**: Live market feed for NIFTY 50 and INDIA VIX
- **📉 Time-Series Analysis**: 3-minute interval OI difference tracking
- **🎯 Volatility Calculator**: Expected move calculations (15-min & 5-min candles)
- **🗄️ Database Connection Pooling**: Efficient MySQL operations
- **🕒 Market Hours Detection**: Automatically pauses during non-market hours
- **📝 Comprehensive Logging**: Structured logging for debugging

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Edit `.env` with your credentials:
```env
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=analyzer_db
```

### 3. Setup Database
```bash
python setup_database.py
```

### 4. Start Data Collection
```bash
python main.py
```

### 5. Start Dashboard API
```bash
cd dashboard
python api.py
```

### 6. Open Dashboard
Navigate to: `dashboard/index.html` in your browser

## Project Structure

```
IndexDataAnalyser/
├── dashboard/              # Real-time web dashboard
│   ├── api.py             # Flask REST API (port 5000)
│   ├── index.html         # Main dashboard (OI Difference Live)
│   └── option_chain.html  # Option Chain view
│
├── core/                  # Core application logic
│   ├── config.py          # Configuration management
│   ├── database.py        # Database connection pool
│   ├── option_chain.py    # Option chain data fetching
│   ├── trade_sync.py      # Trade synchronization
│   └── Utilities.py       # Helper functions
│
├── streaming/             # WebSocket implementation
│   └── market_feed_websocket.py  # Real-time market feed
│
├── sql/                   # Database schemas
├── docs/                  # Documentation
├── main.py                # Main entry point
└── README.md              # This file
```

📖 **Detailed structure**: See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

## Dashboard Features

### Main Dashboard (OI Difference Live)
- **Time-Series View**: 3-minute interval OI and Volume changes
- **Fixed Strike Column**: Easy navigation with vertical scrolling
- **Horizontal Timeline**: Scroll through historical data
- **Jump to Latest**: Quick access to most recent data
- **ATM Highlighting**: Visual indication of at-the-money strike

### Option Chain View
- **Live OI Data**: Call and Put open interest
- **Greeks Display**: Delta, Gamma, Theta, Vega
- **IV Analysis**: Implied volatility tracking
- **Signal Indicators**: BULLISH/BEARISH/NEUTRAL signals

### VIX Volatility Calculator
Displays expected NIFTY moves with 95% probability:
- **15-Min Candle**: Expected move for 15-minute timeframe
- **5-Min Candle**: Expected move for 5-minute timeframe

**Formula**:
- 1 SD = VIX / √(252 × trading_minutes_per_year / candle_minutes)
- 2 SD = 1 SD × 2 (95% confidence)
- Points = (2 SD / 100) × Spot Price

## API Endpoints

The dashboard API (`dashboard/api.py`) provides:

| Endpoint | Description |
|----------|-------------|
| `/api/health` | Health check |
| `/api/spot-price` | NIFTY spot price, % change, VIX |
| `/api/option-chain` | Current option chain data |
| `/api/expiry-dates` | Available expiry dates |
| `/api/oi-difference-live` | Time-series OI difference data |

## Database Tables

1. **nifty_oc_historical**: Option chain historical data
   - Strike price, OI, Volume, IV, Greeks (CE/PE)
   - Updated every 1 minute during market hours

2. **market_feed_realtime**: Real-time tick data
   - NIFTY 50 LTP, volume, OHLC
   - INDIA VIX LTP, volume, OHLC
   - Updated via WebSocket streaming

3. **User_**: Trade data
   - Positions, orders, holdings

## How It Works

### Data Collection (main.py)
1. Connects to Dhan API with credentials
2. Starts WebSocket connection for real-time data
3. Fetches option chain data every minute
4. Stores data in MySQL database
5. Auto-pauses outside market hours (9:15 AM - 3:30 PM IST)

### Dashboard (dashboard/api.py)
1. Serves REST API for frontend
2. Queries database for latest data
3. Calculates OI differences and changes
4. Provides real-time updates to browser

### Frontend (dashboard/*.html)
1. Fetches data from API every 3-5 seconds
2. Renders interactive tables and charts
3. Highlights ATM strikes and significant changes
4. Calculates and displays volatility metrics

## Configuration

All settings are in `.env`:

```env
# Dhan API Credentials
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token

# Database Configuration
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=analyzer_db

# Application Settings
LOG_LEVEL=INFO
DEBUG=True
TRADE_SYNC_INTERVAL=60
DATA_FETCH_INTERVAL=60
STRIKE_RANGE=750
```

## Requirements

- Python 3.8+
- MySQL 8.0+
- Active Dhan trading account
- Modern web browser

## Dependencies

```
dhanhq>=2.0.0
mysql-connector-python>=8.0.33
python-dotenv>=1.0.0
websocket-client>=1.6.0
flask>=3.0.0
flask-cors>=6.0.0
```

## Troubleshooting

### Issue: Dashboard shows "Failed to fetch data"
**Solution**:
1. Ensure `python dashboard/api.py` is running
2. Check that MySQL is running
3. Verify database has data (`python main.py` must run first)

### Issue: No VIX data displayed
**Solution**: VIX data comes from WebSocket. Ensure:
1. WebSocket connection is active in `main.py`
2. `market_feed_realtime` table has recent data

### Issue: "Authentication Failed"
**Solution**:
1. Generate new access token from Dhan
2. Update `DHAN_ACCESS_TOKEN` in `.env`
3. Restart `main.py`

## Documentation

- **Dashboard Setup**: [docs/OI_DASHBOARD_README.md](docs/OI_DASHBOARD_README.md)
- **WebSocket Guide**: [docs/WEBSOCKET_SETUP.md](docs/WEBSOCKET_SETUP.md)
- **Migration Guide**: [docs/MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md)
- **Project Structure**: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

## Key Improvements

### Security
- ✅ Environment-based configuration
- ✅ No hardcoded credentials
- ✅ Proper `.gitignore` rules

### Code Quality
- ✅ Modular package structure
- ✅ Type hints throughout
- ✅ Comprehensive error handling
- ✅ PEP 8 compliant

### Performance
- ✅ Database connection pooling
- ✅ Batch data operations
- ✅ Efficient WebSocket streaming
- ✅ Context managers for resource cleanup

### User Experience
- ✅ Professional dark-themed dashboard
- ✅ Real-time data updates
- ✅ Responsive design
- ✅ Volatility calculations
- ✅ Time-series analysis

## Contributing

When contributing:
1. Follow PEP 8 style guidelines
2. Add type hints to functions
3. Include docstrings
4. Update documentation
5. Test changes thoroughly

## License

[Add your license here]

## Support

For issues or questions:
- Check [docs/](docs/) folder
- Review [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- Open an issue on GitHub

---

**Made with ❤️ for options traders**
