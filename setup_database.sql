-- ============================================================
-- Index Data Analyser - Database Setup Script
-- This script creates the database and all required tables
-- ============================================================

-- Create database
CREATE DATABASE IF NOT EXISTS analyzer_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE analyzer_db;

-- ============================================================
-- Table: nifty_oc_historical
-- Stores historical NIFTY option chain data
-- ============================================================
CREATE TABLE IF NOT EXISTS nifty_oc_historical (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Date DATE NOT NULL,
    Time TIME NOT NULL,
    Strike_price DECIMAL(10, 2) NOT NULL,
    Spot_price DECIMAL(10, 2),

    -- Call Option (CE) Data
    ce_oi BIGINT,
    ce_volume BIGINT,
    ce_IV DECIMAL(10, 4),
    ce_delta DECIMAL(10, 4),
    ce_gamma DECIMAL(10, 6),
    ce_theta DECIMAL(10, 4),
    ce_price DECIMAL(10, 2),
    ce_vega DECIMAL(10, 4),
    ce_signal VARCHAR(50),

    -- Put Option (PE) Data
    pe_oi BIGINT,
    pe_volume BIGINT,
    pe_IV DECIMAL(10, 4),
    pe_delta DECIMAL(10, 4),
    pe_gamma DECIMAL(10, 6),
    pe_theta DECIMAL(10, 4),
    pe_price DECIMAL(10, 2),
    pe_vega DECIMAL(10, 4),
    pe_signal VARCHAR(50),

    -- Computed Column
    OI_Diff BIGINT AS (ce_oi - pe_oi) VIRTUAL,

    -- Indexes for performance
    INDEX idx_date_time (Date, Time),
    INDEX idx_strike (Strike_price),
    INDEX idx_date_time_strike (Date, Time, Strike_price),

    -- Unique constraint to prevent duplicate entries
    UNIQUE KEY unique_entry (Date, Time, Strike_price)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Table: market_feed_realtime
-- Stores real-time market data from WebSocket feed
-- ============================================================
CREATE TABLE IF NOT EXISTS market_feed_realtime (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Market identifier
    symbol VARCHAR(50) NOT NULL,

    -- Timestamp
    last_update_time DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),

    -- Price data
    ltp DECIMAL(10, 2),
    open_price DECIMAL(10, 2),
    high_price DECIMAL(10, 2),
    low_price DECIMAL(10, 2),
    close_price DECIMAL(10, 2),

    -- Volume data
    volume BIGINT,
    avg_price DECIMAL(10, 2),
    total_buy_qty BIGINT,
    total_sell_qty BIGINT,

    -- Change data
    change_value DECIMAL(10, 2),
    change_percent DECIMAL(10, 4),

    -- Indexes
    INDEX idx_symbol (symbol),
    INDEX idx_update_time (last_update_time),
    UNIQUE KEY unique_symbol (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Insert default market symbols
-- ============================================================
INSERT IGNORE INTO market_feed_realtime (symbol) VALUES
    ('NIFTY'),
    ('INDIA VIX'),
    ('NIFTY BANK'),
    ('RELIANCE'),
    ('HDFC BANK'),
    ('ICICI BANK'),
    ('INFOSYS'),
    ('TCS'),
    ('ITC'),
    ('L&T');

-- ============================================================
-- Display table information
-- ============================================================
SHOW TABLES;
SELECT 'Database setup completed successfully!' as Status;
