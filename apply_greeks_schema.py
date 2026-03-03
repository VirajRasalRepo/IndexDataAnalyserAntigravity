"""
Apply Greeks schema updates to the database.
"""

import mysql.connector
from core.config import Config

def apply_schema_updates():
    """Apply Greeks schema updates."""
    print("=" * 60)
    print("Greeks Schema Update")
    print("=" * 60)

    try:
        # Connect to database
        conn = mysql.connector.connect(**Config.get_db_config())
        cursor = conn.cursor()

        # Execute ALTER TABLE for Greeks columns
        print("\n[1/3] Adding Greeks columns to nifty_oc_historical...")

        alter_statements = [
            # Timestamp and DTE
            "ALTER TABLE nifty_oc_historical ADD COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE nifty_oc_historical ADD COLUMN dte INT",
            "ALTER TABLE nifty_oc_historical ADD COLUMN charm DECIMAL(10, 6) DEFAULT 0.0",

            # CE Greeks metrics
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_rank_label VARCHAR(20)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_efficiency DECIMAL(10, 4)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_vega_adj_efficiency DECIMAL(10, 4)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_charm_bleed_60m DECIMAL(10, 6)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_gamma_risk_score DECIMAL(10, 4)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_oi_change BIGINT DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_delta_velocity DECIMAL(10, 6) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_gamma_velocity DECIMAL(10, 6) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_theta_velocity DECIMAL(10, 6) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_iv_velocity DECIMAL(10, 6) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_alert_theta_trap TINYINT(1) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_alert_gamma_blast TINYINT(1) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_alert_negative_carry TINYINT(1) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN ce_alert_lotto_flag TINYINT(1) DEFAULT 0",

            # PE Greeks metrics
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_rank_label VARCHAR(20)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_efficiency DECIMAL(10, 4)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_vega_adj_efficiency DECIMAL(10, 4)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_charm_bleed_60m DECIMAL(10, 6)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_gamma_risk_score DECIMAL(10, 4)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_oi_change BIGINT DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_delta_velocity DECIMAL(10, 6) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_gamma_velocity DECIMAL(10, 6) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_theta_velocity DECIMAL(10, 6) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_iv_velocity DECIMAL(10, 6) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_alert_theta_trap TINYINT(1) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_alert_gamma_blast TINYINT(1) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_alert_negative_carry TINYINT(1) DEFAULT 0",
            "ALTER TABLE nifty_oc_historical ADD COLUMN pe_alert_lotto_flag TINYINT(1) DEFAULT 0",

            # Market metrics
            "ALTER TABLE nifty_oc_historical ADD COLUMN net_delta_flow DECIMAL(10, 4)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN market_bias VARCHAR(10)",
            "ALTER TABLE nifty_oc_historical ADD COLUMN vix_change_pct DECIMAL(10, 3)",
        ]

        for stmt in alter_statements:
            try:
                cursor.execute(stmt)
                print(".", end="", flush=True)
            except mysql.connector.Error as e:
                if "Duplicate column name" not in str(e):
                    print(f"\n  [WARN] {e}")

        print("\n[OK] Greeks columns added")

        # Create User_ table
        print("\n[2/3] Creating User_ table for portfolio tracking...")
        cursor.execute("""
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("[OK] User_ table created")

        conn.commit()

        # Verify
        print("\n[3/3] Verifying schema updates...")
        cursor.execute("DESCRIBE User_")
        user_cols = cursor.fetchall()
        print(f"[OK] User_ table has {len(user_cols)} columns")

        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'analyzer_db'
              AND TABLE_NAME = 'nifty_oc_historical'
              AND COLUMN_NAME LIKE '%efficiency%'
        """)
        greek_count = cursor.fetchone()[0]
        print(f"[OK] Found {greek_count} efficiency columns in nifty_oc_historical")

        cursor.close()
        conn.close()

        print("\n" + "=" * 60)
        print("[SUCCESS] Greeks schema update completed!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(apply_schema_updates())
