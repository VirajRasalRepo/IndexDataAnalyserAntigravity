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
-- Note: Wide format with columns for each instrument (required by WebSocket code)
-- ============================================================
CREATE TABLE IF NOT EXISTS market_feed_realtime (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),

    -- India VIX
    india_vix_ltp DECIMAL(10, 2),
    india_vix_volume BIGINT,
    india_vix_open DECIMAL(10, 2),
    india_vix_high DECIMAL(10, 2),
    india_vix_low DECIMAL(10, 2),
    india_vix_close DECIMAL(10, 2),

    -- Nifty 50
    nifty_50_ltp DECIMAL(10, 2),
    nifty_50_volume BIGINT,
    nifty_50_open DECIMAL(10, 2),
    nifty_50_high DECIMAL(10, 2),
    nifty_50_low DECIMAL(10, 2),
    nifty_50_close DECIMAL(10, 2),

    -- Reliance
    reliance_ltp DECIMAL(10, 2),
    reliance_volume BIGINT,
    reliance_open DECIMAL(10, 2),
    reliance_high DECIMAL(10, 2),
    reliance_low DECIMAL(10, 2),
    reliance_close DECIMAL(10, 2),
    reliance_avg_price DECIMAL(10, 2),
    reliance_total_buy_qty BIGINT,
    reliance_total_sell_qty BIGINT,

    -- HDFC Bank
    hdfc_bank_ltp DECIMAL(10, 2),
    hdfc_bank_volume BIGINT,
    hdfc_bank_open DECIMAL(10, 2),
    hdfc_bank_high DECIMAL(10, 2),
    hdfc_bank_low DECIMAL(10, 2),
    hdfc_bank_close DECIMAL(10, 2),
    hdfc_bank_avg_price DECIMAL(10, 2),
    hdfc_bank_total_buy_qty BIGINT,
    hdfc_bank_total_sell_qty BIGINT,

    -- ICICI Bank
    icici_bank_ltp DECIMAL(10, 2),
    icici_bank_volume BIGINT,
    icici_bank_open DECIMAL(10, 2),
    icici_bank_high DECIMAL(10, 2),
    icici_bank_low DECIMAL(10, 2),
    icici_bank_close DECIMAL(10, 2),
    icici_bank_avg_price DECIMAL(10, 2),
    icici_bank_total_buy_qty BIGINT,
    icici_bank_total_sell_qty BIGINT,

    -- Infosys
    infosys_ltp DECIMAL(10, 2),
    infosys_volume BIGINT,
    infosys_open DECIMAL(10, 2),
    infosys_high DECIMAL(10, 2),
    infosys_low DECIMAL(10, 2),
    infosys_close DECIMAL(10, 2),
    infosys_avg_price DECIMAL(10, 2),
    infosys_total_buy_qty BIGINT,
    infosys_total_sell_qty BIGINT,

    -- TCS
    tcs_ltp DECIMAL(10, 2),
    tcs_volume BIGINT,
    tcs_open DECIMAL(10, 2),
    tcs_high DECIMAL(10, 2),
    tcs_low DECIMAL(10, 2),
    tcs_close DECIMAL(10, 2),
    tcs_avg_price DECIMAL(10, 2),
    tcs_total_buy_qty BIGINT,
    tcs_total_sell_qty BIGINT,

    -- ITC
    itc_ltp DECIMAL(10, 2),
    itc_volume BIGINT,
    itc_open DECIMAL(10, 2),
    itc_high DECIMAL(10, 2),
    itc_low DECIMAL(10, 2),
    itc_close DECIMAL(10, 2),
    itc_avg_price DECIMAL(10, 2),
    itc_total_buy_qty BIGINT,
    itc_total_sell_qty BIGINT,

    -- L&T
    lt_ltp DECIMAL(10, 2),
    lt_volume BIGINT,
    lt_open DECIMAL(10, 2),
    lt_high DECIMAL(10, 2),
    lt_low DECIMAL(10, 2),
    lt_close DECIMAL(10, 2),
    lt_avg_price DECIMAL(10, 2),
    lt_total_buy_qty BIGINT,
    lt_total_sell_qty BIGINT,

    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Display table information
-- ============================================================
SHOW TABLES;
SELECT 'Database setup completed successfully!' as Status;
