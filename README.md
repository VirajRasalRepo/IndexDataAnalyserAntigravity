# Index Data Analyser

A professional Python application for fetching and storing Nifty option chain data and trade information from the Dhan API.

## Features

- **Real-time Option Chain Data**: Fetches and stores NIFTY option chain data including OI, volume, IV, and Greeks
- **Trade Synchronization**: Automatically syncs trades from Dhan trading account
- **Database Connection Pooling**: Efficient database operations with connection pooling
- **Market Hours Detection**: Automatically pauses during non-market hours
- **Comprehensive Logging**: Structured logging for debugging and monitoring
- **Secure Configuration**: Environment-based configuration management

## Project Structure

```
IndexDataAnalyser/
├── main.py              # Main application entry point
├── config.py            # Configuration management
├── database.py          # Database connection handling
├── trade_sync.py        # Trade synchronization logic
├── option_chain.py      # Option chain data fetching
├── Utilities.py         # Utility functions
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── .env                 # Your actual credentials (git-ignored)
└── .gitignore          # Git ignore rules
```

## Installation

### 1. Clone the repository

```bash
cd IndexDataAnalyser
```

### 2. Create virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env  # On Windows: copy .env.example .env
```

Edit `.env` and add your credentials:

```env
DHAN_CLIENT_ID=your_actual_client_id
DHAN_ACCESS_TOKEN=your_actual_access_token
DB_PASSWORD=your_database_password
```

### 5. Set up database

Ensure your MySQL database is running and the required tables exist:

```sql
-- USER_TRADES table
CREATE TABLE IF NOT EXISTS USER_TRADES (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trade_id VARCHAR(50) NOT NULL,
    order_id VARCHAR(50) NOT NULL UNIQUE,
    symbol VARCHAR(50),
    transaction_type VARCHAR(10),
    quantity INT,
    entry_price DECIMAL(10, 2),
    entry_time VARCHAR(50),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NIFTY_OC_HISTORICAL table
CREATE TABLE IF NOT EXISTS NIFTY_OC_HISTORICAL (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Date DATE,
    Time TIME,
    Spot_price DECIMAL(10, 2),
    Strike_price DECIMAL(10, 2),
    ce_oi INT,
    ce_volume INT,
    ce_IV DECIMAL(10, 4),
    ce_delta DECIMAL(10, 4),
    ce_gamma DECIMAL(10, 4),
    ce_theta DECIMAL(10, 4),
    ce_price DECIMAL(10, 2),
    ce_vega DECIMAL(10, 4),
    pe_oi INT,
    pe_volume INT,
    pe_IV DECIMAL(10, 4),
    pe_delta DECIMAL(10, 4),
    pe_gamma DECIMAL(10, 4),
    pe_theta DECIMAL(10, 4),
    pe_price DECIMAL(10, 2),
    pe_vega DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Usage

Run the application:

```bash
python main.py
```

The application will:
1. Initialize database connection pool
2. Connect to Dhan API
3. Fetch current expiry date
4. Start data collection loop:
   - Sync trades every 60 seconds
   - Fetch option chain data every 4 seconds
   - Auto-pause during non-market hours

## Configuration Options

Edit `.env` to customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `TRADE_SYNC_INTERVAL` | 60 | Seconds between trade syncs |
| `DATA_FETCH_INTERVAL` | 4 | Seconds between OI data fetches |
| `STRIKE_RANGE` | 750 | Strike price range around ATM |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Key Improvements from Original

### Security
- ✅ No hardcoded credentials
- ✅ Environment-based configuration
- ✅ `.gitignore` prevents credential commits

### Code Quality
- ✅ Modular architecture (separation of concerns)
- ✅ Type hints for better IDE support
- ✅ Comprehensive docstrings
- ✅ PEP 8 compliant naming conventions
- ✅ Proper error handling with custom exceptions

### Performance
- ✅ Database connection pooling
- ✅ Batch inserts for better throughput
- ✅ Efficient resource management with context managers

### Maintainability
- ✅ Structured logging instead of print statements
- ✅ Constants extracted to configuration
- ✅ Clear separation of business logic
- ✅ Easy to test and extend

## Logging

Logs include:
- Application lifecycle events
- Trade sync status
- Option chain data fetches
- Database operations
- Error conditions with stack traces

Log level can be adjusted in `.env`:
```env
LOG_LEVEL=DEBUG  # For detailed debugging
LOG_LEVEL=INFO   # For normal operation
LOG_LEVEL=WARNING  # Only warnings and errors
```

## Troubleshooting

### Configuration Error
```
ConfigurationError: Missing required configuration: DHAN_CLIENT_ID
```
**Solution**: Ensure `.env` file exists and contains all required variables

### Database Connection Error
```
Failed to create connection pool: Access denied for user
```
**Solution**: Check database credentials in `.env` file

### Market Hours
If the application shows "Outside market hours", it will automatically wait. To disable market hours check for testing, modify `is_market_hours()` in [main.py](main.py).

## Contributing

When making changes:
1. Follow PEP 8 style guidelines
2. Add type hints to function signatures
3. Include docstrings for new functions/classes
4. Update tests if applicable

## License

[Add your license here]

## Support

For issues or questions, please open an issue in the repository.
