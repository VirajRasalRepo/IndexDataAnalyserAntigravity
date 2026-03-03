"""
Quick script to check if Greeks data is populated in the database
"""
import mysql.connector
from core.config import Config

def check_greeks_data():
    """Check if ce_efficiency is populated for specific dates"""

    # Connect to database
    conn = mysql.connector.connect(**Config.get_db_config())
    cursor = conn.cursor(dictionary=True)

    # Query for March 2, Feb 26-27
    query = """
        SELECT
            Date,
            COUNT(*) as total_rows,
            SUM(CASE WHEN ce_efficiency IS NOT NULL THEN 1 ELSE 0 END) as rows_with_greeks,
            SUM(CASE WHEN ce_oi IS NOT NULL THEN 1 ELSE 0 END) as rows_with_oi_data,
            MIN(Time) as earliest_time,
            MAX(Time) as latest_time
        FROM nifty_oc_historical
        WHERE Date IN ('2026-03-02', '2026-02-26', '2026-02-27')
        GROUP BY Date
        ORDER BY Date DESC
    """

    cursor.execute(query)
    results = cursor.fetchall()

    print("\n" + "="*80)
    print("Greeks Data Status in Database")
    print("="*80)

    if not results:
        print("\n[X] No data found for March 2, February 26-27")
    else:
        for row in results:
            print(f"\nDate: {row['Date']}")
            print(f"   Total Rows: {row['total_rows']}")
            print(f"   Rows with Greeks Data (ce_efficiency): {row['rows_with_greeks']}")
            print(f"   Rows with OI Data (ce_oi): {row['rows_with_oi_data']}")
            print(f"   Time Range: {row['earliest_time']} to {row['latest_time']}")

            if row['rows_with_greeks'] == 0:
                print(f"   [!] Greeks NOT calculated - ce_efficiency is NULL")
            else:
                print(f"   [OK] Greeks data available")

    # Check what the available-dates endpoint would return
    print("\n" + "="*80)
    print("Testing available-dates endpoint query")
    print("="*80)

    query2 = """
        SELECT DISTINCT Date
        FROM nifty_oc_historical
        WHERE ce_efficiency IS NOT NULL
        AND Date IN ('2026-03-02', '2026-02-26', '2026-02-27')
        ORDER BY Date DESC
    """

    cursor.execute(query2)
    available = cursor.fetchall()

    if available:
        print("\n[OK] Dates that WOULD appear in calendar:")
        for row in available:
            print(f"   - {row['Date']}")
    else:
        print("\n[X] No dates would appear in calendar (ce_efficiency is NULL for all rows)")
        print("\n[!] Solution: Run main.py during market hours to calculate and save Greeks data")

    cursor.close()
    conn.close()
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    check_greeks_data()
