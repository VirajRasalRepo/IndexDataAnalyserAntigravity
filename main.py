"""
Index Data Analyser - Main Application
Fetches and stores Nifty option chain data and trade information.
"""

import logging
import sys
import time
from datetime import datetime, time as dt_time, timedelta, date as dt_date
from dhanhq import dhanhq

from core import Utilities
from core.config import Config
from core.database import DatabaseManager
from core.trade_sync import TradeSync, TradeSyncError
from core.option_chain import OptionChainData, OptionChainError
from core.greeks_processor import process_greeks_from_db
from streaming.market_feed_websocket import DhanMarketFeed, MarketFeedError

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def is_trading_day(date_to_check: datetime = None) -> bool:
    """
    Check if a given date is a trading day (not weekend or holiday).

    Args:
        date_to_check: Date to check (defaults to today)

    Returns:
        True if it's a trading day, False otherwise
    """
    if date_to_check is None:
        date_to_check = datetime.now()

    # Check if it's a weekend (Saturday=5, Sunday=6)
    if date_to_check.weekday() >= 5:
        return False

    # Check if it's a market holiday
    date_str = date_to_check.strftime("%Y-%m-%d")
    if date_str in Config.MARKET_HOLIDAYS:
        return False

    return True


def is_market_hours() -> bool:
    """
    Check if current time is within market hours (9:15 AM - 3:30 PM IST)
    and today is a trading day (not weekend or holiday).

    Returns:
        True if within market hours, False otherwise
    """
    now = datetime.now()
    current_time = now.time()

    market_start = dt_time(
        Config.MARKET_START_HOUR,
        Config.MARKET_START_MINUTE
    )
    market_end = dt_time(
        Config.MARKET_END_HOUR,
        Config.MARKET_END_MINUTE
    )

    # Check if it's a trading day (not weekend or holiday)
    if not is_trading_day(now):
        return False

    return market_start <= current_time <= market_end


def get_next_market_open_time() -> datetime:
    """
    Calculate the next market open time (9:15 AM IST on next trading day).
    Skips weekends and market holidays.

    Returns:
        datetime object representing the next market open time
    """
    now = datetime.now()

    # Start with today's market open time
    next_open = now.replace(
        hour=Config.MARKET_START_HOUR,
        minute=Config.MARKET_START_MINUTE,
        second=0,
        microsecond=0
    )

    # If current time is before market open today and today is a trading day, market opens today
    if now.time() < dt_time(Config.MARKET_START_HOUR, Config.MARKET_START_MINUTE):
        if is_trading_day(now):
            return next_open

    # Otherwise, find next trading day
    next_open = next_open + timedelta(days=1)

    # Skip weekends and holidays
    max_iterations = 30  # Safety limit to avoid infinite loop
    iterations = 0
    while not is_trading_day(next_open) and iterations < max_iterations:
        next_open = next_open + timedelta(days=1)
        iterations += 1

    if iterations >= max_iterations:
        logger.warning(f"Could not find trading day within {max_iterations} days. Using calculated date anyway.")

    return next_open


def get_seconds_until_market_open() -> int:
    """
    Calculate seconds until next market open.

    Returns:
        Number of seconds until market opens
    """
    now = datetime.now()
    next_open = get_next_market_open_time()
    time_until_open = (next_open - now).total_seconds()
    return max(0, int(time_until_open))


def initialize_application() -> tuple[dhanhq, str]:
    """
    Initialize application components.

    Returns:
        Tuple of (dhan_client, expiry_date)

    Raises:
        SystemExit: If initialization fails
    """
    try:
        # Initialize database connection pool
        DatabaseManager.initialize_pool(pool_size=5)
        logger.info("Database connection pool initialized")

        # Initialize Dhan client
        dhan_client = dhanhq(Config.DHAN_CLIENT_ID, Config.DHAN_ACCESS_TOKEN)
        logger.info("Dhan API client initialized")

        # Fetch expiry date
        expiry_data = Utilities.get_expiry_list(dhan_client)
        expiry = (
            expiry_data[0]
            if isinstance(expiry_data, list) and len(expiry_data) > 0
            else expiry_data
        )

        if not expiry:
            logger.error("Failed to fetch expiry list")
            raise ValueError("No expiry date available")

        logger.info(f"Using expiry date: {expiry}")
        return dhan_client, expiry

    except Exception as e:
        logger.critical(f"Application initialization failed: {e}", exc_info=True)
        sys.exit(1)

def run_pipeline():
    """Main application pipeline."""
    logger.info("=" * 60)
    logger.info("Index Data Analyser Started")
    logger.info("=" * 60)

    # Initialize application
    dhan_client, expiry = initialize_application()

    # Initialize sync handlers
    trade_sync = TradeSync(dhan_client)
    option_chain = OptionChainData(dhan_client, expiry)

    # Initialize WebSocket market feed (connects when market is open)
    market_feed = DhanMarketFeed(Config.DHAN_CLIENT_ID, Config.DHAN_ACCESS_TOKEN)
    if is_market_hours():
        market_feed.connect()
        market_feed.start()
        logger.info("Real-time market feed WebSocket started")
    else:
        logger.info("Market closed - WebSocket will start when market opens")

    # Tracking variables
    last_trade_sync_time = 0.0
    iteration_count = 0
    post_market_sync_done = False  # Track if post-market sync is done for the day
    last_sync_date = None  # Track the last date we did post-market sync

    # Greeks processing variables
    prev_greeks_snapshot = {}  # For velocity calculation
    prev_vix = None  # Track previous VIX for velocity

    try:
        logger.info(f"Pipeline active for Expiry: {expiry}")

        while True:
            iteration_count += 1
            current_time = time.time()
            today = datetime.now().date()

            # Reset post-market sync flag if it's a new day
            if last_sync_date != today:
                post_market_sync_done = False
                last_sync_date = today

            # Check market hours (9:15 AM - 3:30 PM IST, Monday-Friday)
            in_market_hours = is_market_hours()

            if not in_market_hours:
                # Allow one final sync after market close to capture today's trades
                if not post_market_sync_done and is_trading_day(datetime.now()):
                    logger.info("Market closed. Performing final trade sync for today...")
                    try:
                        new_trades = trade_sync.sync_trades()
                        if new_trades > 0:
                            logger.info(f"Post-market sync: Synced {new_trades} new trades")
                        else:
                            logger.info("Post-market sync: No new trades to sync")
                        post_market_sync_done = True
                    except TradeSyncError as e:
                        logger.error(f"Post-market trade sync failed: {e}")
                        post_market_sync_done = True  # Mark as done to avoid retry loop

                # After post-market sync, calculate when market opens next
                if Config.DEBUG:
                    logger.debug("Outside market hours but DEBUG mode enabled - continuing")
                else:
                    # Stop WebSocket while market is closed to avoid 429 rate-limiting
                    if market_feed.running:
                        logger.info("Stopping WebSocket feed (market closed)")
                        market_feed.stop()

                    # Calculate next market open time
                    next_open_time = get_next_market_open_time()
                    seconds_until_open = get_seconds_until_market_open()

                    logger.info(f"Market closed. Next market open: {next_open_time.strftime('%Y-%m-%d %H:%M:%S')}")

                    # If market opens in more than 1 hour, sleep until 30 minutes before market open
                    # This allows the program to prepare and ensures we don't miss market open
                    if seconds_until_open > 3600:  # More than 1 hour
                        sleep_duration = max(seconds_until_open - 1800, 300)  # Wake up 30 min early, or 5 min minimum
                        wake_time = datetime.now() + timedelta(seconds=sleep_duration)
                        logger.info(f"Sleeping until {wake_time.strftime('%H:%M:%S')} ({sleep_duration // 60:.0f} minutes)")
                        time.sleep(sleep_duration)
                    else:
                        # Market opens soon, check every 5 minutes
                        logger.info(f"Market opens in {seconds_until_open // 60:.0f} minutes. Checking every 5 minutes...")
                        time.sleep(300)

                    continue

            # Restart WebSocket if it was stopped during market close
            if not market_feed.running:
                logger.info("Restarting WebSocket feed (market open)")
                market_feed.connect()
                market_feed.start()

            try:
                # --- STEP 1: Sync Trades (Every 60 seconds) ---
                if current_time - last_trade_sync_time >= Config.TRADE_SYNC_INTERVAL:
                    try:
                        new_trades = trade_sync.sync_trades()
                        if new_trades > 0:
                            logger.info(f"Synced {new_trades} new trades")
                        last_trade_sync_time = current_time
                    except TradeSyncError as e:
                        logger.error(f"Trade sync failed: {e}")

                # --- STEP 2: Fetch and Store Option Chain Data ---
                try:
                    strikes_stored, spot_price = option_chain.fetch_and_store()
                    logger.info(
                        f"Iteration {iteration_count}: Stored {strikes_stored} strikes "
                        f"(Spot: {spot_price:.2f})"
                    )
                except OptionChainError as e:
                    logger.error(f"Option chain fetch failed: {e}")

                # --- STEP 3: Store Real-time Market Feed Data (WebSocket) ---
                try:
                    market_feed.store_to_database()
                    latest_data = market_feed.get_latest_data()
                    logger.info(f"Real-time feed: Stored data for {len(latest_data)} instruments")
                except MarketFeedError as e:
                    logger.error(f"Market feed store failed: {e}")

                # --- STEP 4: Process Greeks Analytics ---
                try:
                    # Get latest OC data from DB
                    with DatabaseManager.get_cursor() as cursor:
                        cursor.execute("""
                            SELECT *
                            FROM nifty_oc_historical
                            WHERE Date = CURDATE() AND Time = (
                                SELECT t.max_time FROM (SELECT MAX(Time) AS max_time FROM nifty_oc_historical WHERE Date = CURDATE()) t
                            )
                        """)
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()

                        if rows:
                            db_rows = [dict(zip(columns, row)) for row in rows]

                            # Get VIX
                            cursor.execute("""
                                SELECT india_vix_ltp
                                FROM market_feed_realtime
                                ORDER BY timestamp DESC LIMIT 1
                            """)
                            vix_row = cursor.fetchone()
                            vix_current = float(vix_row[0]) if vix_row else 14.0
                            vix_prev_val = prev_vix if prev_vix is not None else vix_current

                            # Calculate PCR
                            cursor.execute("""
                                SELECT
                                    SUM(pe_oi) as pe_oi_total,
                                    SUM(ce_oi) as ce_oi_total
                                FROM nifty_oc_historical
                                WHERE Date = CURDATE() AND Time = (
                                    SELECT t.max_time FROM (SELECT MAX(Time) AS max_time FROM nifty_oc_historical WHERE Date = CURDATE()) t
                                )
                            """)
                            pcr_row = cursor.fetchone()
                            pe_oi_total = float(pcr_row[0] or 1)
                            ce_oi_total = float(pcr_row[1] or 1)
                            pcr = pe_oi_total / ce_oi_total if ce_oi_total > 0 else 1.0

                            # Parse expiry date from Dhan API (already fetched at startup)
                            expiry_date = dt_date.fromisoformat(expiry)

                            # Process Greeks
                            greeks_result = process_greeks_from_db(
                                db_rows=db_rows,
                                spot=spot_price,
                                expiry_date=expiry_date,
                                vix_current=vix_current,
                                vix_prev=vix_prev_val,
                                pcr=pcr,
                                prev_minute_greeks=prev_greeks_snapshot
                            )

                            # Update snapshots for next iteration
                            prev_greeks_snapshot = {
                                f"{r['strike_price']}_{r['option_type']}": r
                                for r in greeks_result['ce_ranked'] + greeks_result['pe_ranked']
                            }
                            prev_vix = vix_current

                            # Save Greeks data back to database
                            # Group by strike price (since each row has both CE and PE data)
                            strikes_by_price = {}
                            for strike_data in greeks_result['ce_ranked'] + greeks_result['pe_ranked']:
                                sp = strike_data['strike_price']
                                if sp not in strikes_by_price:
                                    strikes_by_price[sp] = {'CE': None, 'PE': None}
                                strikes_by_price[sp][strike_data['option_type']] = strike_data

                            with DatabaseManager.get_cursor() as cursor:
                                for strike_price, data in strikes_by_price.items():
                                    ce_data = data.get('CE', {})
                                    pe_data = data.get('PE', {})

                                    # Update both CE and PE Greeks for this strike in one query
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
                                        WHERE Date = CURDATE()
                                          AND Time = (SELECT t.max_time FROM (SELECT MAX(Time) AS max_time FROM nifty_oc_historical WHERE Date = CURDATE()) t)
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
                                        strike_price
                                    ))

                            logger.info(
                                f"Greeks: Bias={greeks_result['trend_intensity']['market_bias']}, "
                                f"Net Δ={greeks_result['trend_intensity']['net_delta_flow']:.3f}, "
                                f"Alerts={len(greeks_result['alerts'])} | Saved to DB"
                            )

                except Exception as e:
                    logger.error(f"Greeks processing failed: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Unexpected error in iteration {iteration_count}: {e}", exc_info=True)

            # Sleep before next iteration
            time.sleep(Config.DATA_FETCH_INTERVAL)

    except KeyboardInterrupt:
        logger.info("\nShutdown signal received. Cleaning up...")
    except Exception as e:
        logger.critical(f"Fatal error in pipeline: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info("Shutting down WebSocket connection...")
        market_feed.stop()
        DatabaseManager.close_pool()
        logger.info("Application shutdown complete")
        sys.exit(0)

if __name__ == "__main__":
    run_pipeline()
