-- Enhanced Market Feed Table with Real-Time Data
-- This table stores comprehensive market data from WebSocket feed

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Explanation:
-- LTP = Last Traded Price
-- Volume = Total traded volume for the day
-- Open/High/Low/Close = OHLC values
-- Avg Price = Average traded price
-- Total Buy/Sell Qty = Total quantities on buy/sell side
