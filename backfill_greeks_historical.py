"""
Backfill Greeks calculations for historical option chain data.
This script processes existing historical data and calculates Greeks that weren't computed in real-time.
"""
import logging
from datetime import datetime, date as dt_date
from dhanhq import dhanhq
from core.config import Config
from core import Utilities
from core.greeks_processor import process_greeks_from_db
from core.database import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_greeks_for_timestamp(target_date, target_time, expiry_date):
    """
    Calculate Greeks for a specific timestamp.

    Args:
        target_date: Date to process (datetime.date or string YYYY-MM-DD)
        target_time: Time to process (datetime.time or string HH:MM:SS)
        expiry_date: Expiry date for Greeks calculation (datetime.date)
    """
    # Get option chain data from database
    with DatabaseManager.get_cursor() as cursor:
        cursor.execute("""
            SELECT *
            FROM nifty_oc_historical
            WHERE Date = %s AND Time = %s
        """, (target_date, target_time))

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        if not rows:
            return 0

        # Convert column names to lowercase for greeks processor compatibility
        db_rows = [{col.lower(): val for col, val in zip(columns, row)} for row in rows]

        # Get spot price from the data
        spot_price = float(db_rows[0].get('spot_price', 0)) if db_rows else 0.0
        if spot_price == 0:
            logger.warning(f"No spot price for {target_date} {target_time}")
            return 0

        # Use default VIX if not available
        vix_current = 14.0
        vix_prev = 14.0

        # Calculate PCR
        cursor.execute("""
            SELECT
                SUM(pe_oi) as pe_oi_total,
                SUM(ce_oi) as ce_oi_total
            FROM nifty_oc_historical
            WHERE Date = %s AND Time = %s
        """, (target_date, target_time))

        pcr_row = cursor.fetchone()
        pe_oi_total = float(pcr_row[0] or 1)
        ce_oi_total = float(pcr_row[1] or 1)
        pcr = pe_oi_total / ce_oi_total if ce_oi_total > 0 else 1.0

    # Process Greeks
    greeks_result = process_greeks_from_db(
        db_rows=db_rows,
        spot=spot_price,
        expiry_date=expiry_date,
        vix_current=vix_current,
        vix_prev=vix_prev,
        pcr=pcr,
        prev_minute_greeks=None
    )

    # Save Greeks data back to database
    strikes_by_price = {}
    for strike_data in greeks_result['ce_ranked'] + greeks_result['pe_ranked']:
        sp = strike_data['strike_price']
        if sp not in strikes_by_price:
            strikes_by_price[sp] = {'CE': None, 'PE': None}
        strikes_by_price[sp][strike_data['option_type']] = strike_data

    update_count = 0
    with DatabaseManager.get_cursor() as cursor:
        for strike_price, data in strikes_by_price.items():
            ce_data = data.get('CE', {}) or {}
            pe_data = data.get('PE', {}) or {}

            cursor.execute("""
                UPDATE nifty_oc_historical
                SET
                    dte = %s,
                    ce_efficiency = %s,
                    ce_vega_adj_efficiency = %s,
                    ce_delta_velocity = %s,
                    ce_gamma_velocity = %s,
                    ce_theta_velocity = %s,
                    ce_iv_velocity = %s,
                    ce_alert_theta_trap = %s,
                    ce_alert_gamma_blast = %s,
                    ce_alert_negative_carry = %s,
                    pe_efficiency = %s,
                    pe_vega_adj_efficiency = %s,
                    pe_delta_velocity = %s,
                    pe_gamma_velocity = %s,
                    pe_theta_velocity = %s,
                    pe_iv_velocity = %s,
                    pe_alert_theta_trap = %s,
                    pe_alert_gamma_blast = %s,
                    pe_alert_negative_carry = %s
                WHERE Date = %s
                  AND Time = %s
                  AND Strike_price = %s
            """, (
                greeks_result['dte'],
                # CE columns
                ce_data.get('efficiency') if ce_data else None,
                ce_data.get('vega_adj_efficiency') if ce_data else None,
                ce_data.get('delta_velocity', 0.0) if ce_data else 0.0,
                ce_data.get('gamma_velocity', 0.0) if ce_data else 0.0,
                ce_data.get('theta_velocity', 0.0) if ce_data else 0.0,
                ce_data.get('iv_velocity', 0.0) if ce_data else 0.0,
                ce_data.get('alert_theta_trap', False) if ce_data else False,
                ce_data.get('alert_gamma_blast', False) if ce_data else False,
                ce_data.get('alert_negative_carry', False) if ce_data else False,
                # PE columns
                pe_data.get('efficiency') if pe_data else None,
                pe_data.get('vega_adj_efficiency') if pe_data else None,
                pe_data.get('delta_velocity', 0.0) if pe_data else 0.0,
                pe_data.get('gamma_velocity', 0.0) if pe_data else 0.0,
                pe_data.get('theta_velocity', 0.0) if pe_data else 0.0,
                pe_data.get('iv_velocity', 0.0) if pe_data else 0.0,
                pe_data.get('alert_theta_trap', False) if pe_data else False,
                pe_data.get('alert_gamma_blast', False) if pe_data else False,
                pe_data.get('alert_negative_carry', False) if pe_data else False,
                # WHERE clause
                target_date, target_time, strike_price
            ))
            update_count += 1

    return update_count


def backfill_greeks_for_date(target_date, expiry_date):
    """
    Calculate Greeks for all timestamps on a specific date.

    Args:
        target_date: Date to process (datetime.date or string YYYY-MM-DD)
        expiry_date: Expiry date for Greeks calculation (datetime.date or string)
    """
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    if isinstance(expiry_date, str):
        expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()

    logger.info(f"\nProcessing: {target_date} (Expiry: {expiry_date})")

    # Get distinct timestamps for this date
    with DatabaseManager.get_cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT Time
            FROM nifty_oc_historical
            WHERE Date = %s
            ORDER BY Time ASC
        """, (target_date,))

        timestamps = [row[0] for row in cursor.fetchall()]

    if not timestamps:
        logger.warning(f"  No data found")
        return

    logger.info(f"  Found {len(timestamps)} timestamps")

    # Process each timestamp
    total_updates = 0
    for i, timestamp in enumerate(timestamps, 1):
        try:
            updates = backfill_greeks_for_timestamp(target_date, timestamp, expiry_date)
            total_updates += updates

            if i % 10 == 0:
                logger.info(f"  Progress: {i}/{len(timestamps)} timestamps...")
        except Exception as e:
            logger.error(f"  Error at {timestamp}: {e}")
            continue

    logger.info(f"  Completed: {total_updates} strike prices updated")


def main():
    """Main backfill function"""
    logger.info("\n" + "="*80)
    logger.info("Greeks Historical Data Backfill")
    logger.info("="*80 + "\n")

    # Initialize database connection pool
    try:
        DatabaseManager.initialize_pool()
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return

    # Initialize Dhan client
    try:
        dhan_client = dhanhq(Config.DHAN_CLIENT_ID, Config.DHAN_ACCESS_TOKEN)
        logger.info("Dhan client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Dhan client: {e}")
        return

    # Get expiry date (use latest from Dhan API)
    try:
        expiry_data = Utilities.get_expiry_list(dhan_client)
        expiry_str = expiry_data[0] if isinstance(expiry_data, list) and len(expiry_data) > 0 else expiry_data
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date() if expiry_str else datetime.now().date()
        logger.info(f"Using expiry date: {expiry_date}\n")
    except Exception as e:
        logger.error(f"Failed to fetch expiry: {e}")
        return

    # Get dates to backfill (dates with data but no Greeks)
    with DatabaseManager.get_cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT Date
            FROM nifty_oc_historical
            WHERE ce_efficiency IS NULL
              AND ce_oi IS NOT NULL
            ORDER BY Date DESC
            LIMIT 30
        """)

        dates_to_process = [row[0] for row in cursor.fetchall()]

    if not dates_to_process:
        logger.info("No dates found that need Greeks backfill")
        return

    logger.info(f"Found {len(dates_to_process)} dates to process:")
    for date in dates_to_process:
        logger.info(f"  - {date}")

    print("\nDo you want to proceed with backfill? (yes/no): ", end='')
    confirm = input().strip().lower()

    if confirm != 'yes':
        logger.info("\nBackfill cancelled")
        return

    logger.info("\n" + "="*80)
    logger.info("Starting Backfill...")
    logger.info("="*80)

    # Process each date
    for i, date in enumerate(dates_to_process, 1):
        logger.info(f"\n[{i}/{len(dates_to_process)}] {date}")
        backfill_greeks_for_date(date, expiry_date)

    logger.info("\n" + "="*80)
    logger.info("Backfill Complete!")
    logger.info("="*80)
    logger.info("\nYou can now view historical Greeks data in the dashboard")


if __name__ == "__main__":
    main()
