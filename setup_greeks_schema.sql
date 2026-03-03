-- ===============================================================
-- Greeks Analytics Schema Update
-- Adds derived Greeks metrics columns to nifty_oc_historical
-- ===============================================================

USE analyzer_db;

-- Add new columns for Greeks analytics (if they don't exist)
ALTER TABLE nifty_oc_historical
    ADD COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp for Greeks processing',
    ADD COLUMN dte INT COMMENT 'Days to expiry',
    ADD COLUMN charm DECIMAL(10, 6) DEFAULT 0.0 COMMENT 'Charm (delta decay over time)',

    -- CE-specific derived metrics
    ADD COLUMN ce_rank_label VARCHAR(20) COMMENT 'CE: ATM/ITM/OTM/Deep_ITM/Scalp',
    ADD COLUMN ce_efficiency DECIMAL(10, 4) COMMENT 'CE: Delta/|Theta| ratio',
    ADD COLUMN ce_vega_adj_efficiency DECIMAL(10, 4) COMMENT 'CE: Vega-adjusted efficiency',
    ADD COLUMN ce_charm_bleed_60m DECIMAL(10, 6) COMMENT 'CE: Delta loss in 60 min',
    ADD COLUMN ce_gamma_risk_score DECIMAL(10, 4) COMMENT 'CE: Gamma risk score',
    ADD COLUMN ce_oi_change BIGINT DEFAULT 0 COMMENT 'CE: OI change',
    ADD COLUMN ce_delta_velocity DECIMAL(10, 6) DEFAULT 0 COMMENT 'CE: Delta change/min',
    ADD COLUMN ce_gamma_velocity DECIMAL(10, 6) DEFAULT 0 COMMENT 'CE: Gamma change/min',
    ADD COLUMN ce_theta_velocity DECIMAL(10, 6) DEFAULT 0 COMMENT 'CE: Theta change/min',
    ADD COLUMN ce_iv_velocity DECIMAL(10, 6) DEFAULT 0 COMMENT 'CE: IV change/min',
    ADD COLUMN ce_alert_theta_trap TINYINT(1) DEFAULT 0 COMMENT 'CE: Theta trap flag',
    ADD COLUMN ce_alert_gamma_blast TINYINT(1) DEFAULT 0 COMMENT 'CE: Gamma blast flag',
    ADD COLUMN ce_alert_negative_carry TINYINT(1) DEFAULT 0 COMMENT 'CE: Negative carry flag',
    ADD COLUMN ce_alert_lotto_flag TINYINT(1) DEFAULT 0 COMMENT 'CE: Lotto scalp flag',

    -- PE-specific derived metrics
    ADD COLUMN pe_rank_label VARCHAR(20) COMMENT 'PE: ATM/ITM/OTM/Deep_ITM/Scalp',
    ADD COLUMN pe_efficiency DECIMAL(10, 4) COMMENT 'PE: Delta/|Theta| ratio',
    ADD COLUMN pe_vega_adj_efficiency DECIMAL(10, 4) COMMENT 'PE: Vega-adjusted efficiency',
    ADD COLUMN pe_charm_bleed_60m DECIMAL(10, 6) COMMENT 'PE: Delta loss in 60 min',
    ADD COLUMN pe_gamma_risk_score DECIMAL(10, 4) COMMENT 'PE: Gamma risk score',
    ADD COLUMN pe_oi_change BIGINT DEFAULT 0 COMMENT 'PE: OI change',
    ADD COLUMN pe_delta_velocity DECIMAL(10, 6) DEFAULT 0 COMMENT 'PE: Delta change/min',
    ADD COLUMN pe_gamma_velocity DECIMAL(10, 6) DEFAULT 0 COMMENT 'PE: Gamma change/min',
    ADD COLUMN pe_theta_velocity DECIMAL(10, 6) DEFAULT 0 COMMENT 'PE: Theta change/min',
    ADD COLUMN pe_iv_velocity DECIMAL(10, 6) DEFAULT 0 COMMENT 'PE: IV change/min',
    ADD COLUMN pe_alert_theta_trap TINYINT(1) DEFAULT 0 COMMENT 'PE: Theta trap flag',
    ADD COLUMN pe_alert_gamma_blast TINYINT(1) DEFAULT 0 COMMENT 'PE: Gamma blast flag',
    ADD COLUMN pe_alert_negative_carry TINYINT(1) DEFAULT 0 COMMENT 'PE: Negative carry flag',
    ADD COLUMN pe_alert_lotto_flag TINYINT(1) DEFAULT 0 COMMENT 'PE: Lotto scalp flag',

    -- Market-level metrics
    ADD COLUMN net_delta_flow DECIMAL(10, 4) COMMENT 'Net delta flow (CE-PE)',
    ADD COLUMN market_bias VARCHAR(10) COMMENT 'BULLISH/BEARISH/NEUTRAL',
    ADD COLUMN vix_change_pct DECIMAL(10, 3) COMMENT 'VIX % change';

-- Add indices for better query performance (skip if already exist)
-- Note: Run these manually if you get "Duplicate key name" errors
-- CREATE INDEX idx_timestamp_strike ON nifty_oc_historical (timestamp, strike_price);
-- CREATE INDEX idx_date_time_strike ON nifty_oc_historical (Date, Time, Strike_price);

-- ===============================================================
-- Create User_ table for portfolio tracking
-- ===============================================================

CREATE TABLE IF NOT EXISTS User_ (
    trade_id INT AUTO_INCREMENT PRIMARY KEY,
    strike_price DECIMAL(10, 2) NOT NULL,
    option_type ENUM('CE', 'PE') NOT NULL,
    quantity INT NOT NULL,
    entry_price DECIMAL(10, 2) NOT NULL,
    entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    exit_price DECIMAL(10, 2) DEFAULT NULL,
    exit_time DATETIME DEFAULT NULL,
    status ENUM('OPEN', 'CLOSED') DEFAULT 'OPEN',
    pnl DECIMAL(15, 2) DEFAULT NULL,
    notes TEXT,
    INDEX idx_status (status),
    INDEX idx_strike_type (strike_price, option_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User trades for portfolio delta tracking';

-- ===============================================================
-- Verification queries
-- ===============================================================

-- Check new columns were added
SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'analyzer_db'
  AND TABLE_NAME = 'nifty_oc_historical'
  AND COLUMN_NAME LIKE '%efficiency%'
ORDER BY ORDINAL_POSITION;

-- Verify User_ table
DESCRIBE User_;

-- Check table size
SELECT
    COUNT(*) as total_rows,
    MIN(Date) as earliest_date,
    MAX(Date) as latest_date
FROM nifty_oc_historical;

SELECT 'Greeks schema update completed successfully!' as Status;
