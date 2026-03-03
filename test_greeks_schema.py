#!/usr/bin/env python
"""Test script to verify Greeks database schema."""

import sys
from core.database import DatabaseManager

# Initialize database pool
DatabaseManager.initialize_pool()

print("=" * 60)
print("GREEKS DATABASE SCHEMA VERIFICATION")
print("=" * 60)

try:
    with DatabaseManager.get_cursor() as cursor:
        # Check efficiency columns
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'nifty_oc_historical'
              AND COLUMN_NAME LIKE '%efficiency%'
        """)
        columns = cursor.fetchall()

        print("\n[OK] Greeks Efficiency Columns:")
        for col in columns:
            print(f"  - {col[0]}")

        # Check User_ table
        cursor.execute("SHOW TABLES LIKE 'User_%'")
        tables = cursor.fetchall()

        print("\n[OK] User_ Table:")
        for table in tables:
            print(f"  - {table[0]}")

        # Check User_ table structure
        if tables:
            cursor.execute("DESCRIBE User_")
            user_columns = cursor.fetchall()
            print("\n[OK] User_ Table Columns:")
            for col in user_columns:
                print(f"  - {col[0]} ({col[1]})")

        # Check if any Greeks data exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM nifty_oc_historical
            WHERE ce_efficiency IS NOT NULL
        """)
        count = cursor.fetchone()[0]

        print(f"\n[OK] Rows with Greeks data: {count}")

        print("\n" + "=" * 60)
        print("SCHEMA VERIFICATION COMPLETE")
        print("=" * 60)

except Exception as e:
    print(f"\n[ERROR] {e}")
    sys.exit(1)
finally:
    DatabaseManager.close_pool()
