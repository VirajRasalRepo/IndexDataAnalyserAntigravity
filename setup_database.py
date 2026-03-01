"""
Setup script to create market_feed_realtime table.
"""

import mysql.connector
from core.config import Config

# SQL to create table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS market_feed_realtime (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),

    india_vix_ltp DECIMAL(10, 2),
    india_vix_volume BIGINT,
    india_vix_open DECIMAL(10, 2),
    india_vix_high DECIMAL(10, 2),
    india_vix_low DECIMAL(10, 2),
    india_vix_close DECIMAL(10, 2),

    nifty_50_ltp DECIMAL(10, 2),
    nifty_50_volume BIGINT,
    nifty_50_open DECIMAL(10, 2),
    nifty_50_high DECIMAL(10, 2),
    nifty_50_low DECIMAL(10, 2),
    nifty_50_close DECIMAL(10, 2),

    reliance_ltp DECIMAL(10, 2),
    reliance_volume BIGINT,
    reliance_open DECIMAL(10, 2),
    reliance_high DECIMAL(10, 2),
    reliance_low DECIMAL(10, 2),
    reliance_close DECIMAL(10, 2),
    reliance_avg_price DECIMAL(10, 2),
    reliance_total_buy_qty BIGINT,
    reliance_total_sell_qty BIGINT,

    hdfc_bank_ltp DECIMAL(10, 2),
    hdfc_bank_volume BIGINT,
    hdfc_bank_open DECIMAL(10, 2),
    hdfc_bank_high DECIMAL(10, 2),
    hdfc_bank_low DECIMAL(10, 2),
    hdfc_bank_close DECIMAL(10, 2),
    hdfc_bank_avg_price DECIMAL(10, 2),
    hdfc_bank_total_buy_qty BIGINT,
    hdfc_bank_total_sell_qty BIGINT,

    icici_bank_ltp DECIMAL(10, 2),
    icici_bank_volume BIGINT,
    icici_bank_open DECIMAL(10, 2),
    icici_bank_high DECIMAL(10, 2),
    icici_bank_low DECIMAL(10, 2),
    icici_bank_close DECIMAL(10, 2),
    icici_bank_avg_price DECIMAL(10, 2),
    icici_bank_total_buy_qty BIGINT,
    icici_bank_total_sell_qty BIGINT,

    infosys_ltp DECIMAL(10, 2),
    infosys_volume BIGINT,
    infosys_open DECIMAL(10, 2),
    infosys_high DECIMAL(10, 2),
    infosys_low DECIMAL(10, 2),
    infosys_close DECIMAL(10, 2),
    infosys_avg_price DECIMAL(10, 2),
    infosys_total_buy_qty BIGINT,
    infosys_total_sell_qty BIGINT,

    tcs_ltp DECIMAL(10, 2),
    tcs_volume BIGINT,
    tcs_open DECIMAL(10, 2),
    tcs_high DECIMAL(10, 2),
    tcs_low DECIMAL(10, 2),
    tcs_close DECIMAL(10, 2),
    tcs_avg_price DECIMAL(10, 2),
    tcs_total_buy_qty BIGINT,
    tcs_total_sell_qty BIGINT,

    itc_ltp DECIMAL(10, 2),
    itc_volume BIGINT,
    itc_open DECIMAL(10, 2),
    itc_high DECIMAL(10, 2),
    itc_low DECIMAL(10, 2),
    itc_close DECIMAL(10, 2),
    itc_avg_price DECIMAL(10, 2),
    itc_total_buy_qty BIGINT,
    itc_total_sell_qty BIGINT,

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

def main():
    """Create the market_feed_realtime table."""
    print("Creating market_feed_realtime table...")

    try:
        # Connect to database
        conn = mysql.connector.connect(**Config.get_db_config())
        cursor = conn.cursor()

        # Create table
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()

        print("[OK] Table 'market_feed_realtime' created successfully!")

        # Verify table exists
        cursor.execute("SHOW TABLES LIKE 'market_feed_realtime'")
        result = cursor.fetchone()

        if result:
            print("[OK] Table verified in database")

            # Show column count
            cursor.execute("DESCRIBE market_feed_realtime")
            columns = cursor.fetchall()
            print(f"[OK] Table has {len(columns)} columns")
        else:
            print("[WARN] Table not found after creation")

    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return 0

if __name__ == "__main__":
    exit(main())
