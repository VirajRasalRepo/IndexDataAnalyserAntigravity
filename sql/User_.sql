CREATE TABLE IF NOT EXISTS USER_TRADES (
    trade_id VARCHAR(50) PRIMARY KEY,        -- From Dhan Trade Book
    order_id VARCHAR(50),
    symbol VARCHAR(100) NOT NULL,            -- e.g., 'NIFTY 20MAR 22000 CE'
    transaction_type ENUM('BUY', 'SELL'),
    
    -- Execution Details
    quantity INT NOT NULL,
    entry_price DECIMAL(10, 2) NOT NULL,
    exit_price DECIMAL(10, 2),
    entry_time DATETIME NOT NULL,
    exit_time DATETIME,
    
    -- Analysis Fields
    trade_type ENUM('SCALPING', 'INTRADAY', 'POSITIONAL'),
    strategy_name VARCHAR(50),               -- e.g., 'VWAP_Crossover'
    status ENUM('OPEN', 'CLOSED', 'CANCELLED'),
    
    -- P&L Calculations
    pnl_amount DECIMAL(15, 2) DEFAULT 0.00,
    charges_estimated DECIMAL(10, 2),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


SELECT * FROM analyzer_db.user_trades;
Delete  FROM analyzer_db.user_trades;
TRUNCATE TABLE analyzer_db.user_trades;

DROP TABLE IF EXISTS USER_TRADES;

CREATE TABLE IF NOT EXISTS USER_TRADES (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trade_id VARCHAR(50),
    order_id VARCHAR(50) UNIQUE,
    symbol VARCHAR(100),
    transaction_type VARCHAR(10),
    quantity INT,
    entry_price DECIMAL(10, 2),
    entry_time DATETIME,
    status VARCHAR(50)
);