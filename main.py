"""
Index Data Analyser - Main Application
Fetches and stores Nifty option chain data and trade information.
"""

import logging
import sys
import time
from datetime import datetime, time as dt_time
from dhanhq import dhanhq

import Utilities
from config import Config
from database import DatabaseManager
from trade_sync import TradeSync, TradeSyncError
from option_chain import OptionChainData, OptionChainError
from market_watch import MarketWatchData, MarketWatchError
from market_feed_websocket import DhanMarketFeed, MarketFeedError

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def is_market_hours() -> bool:
    """
    Check if current time is within market hours (9:15 AM - 3:30 PM IST).

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

    # Check if it's a weekday (Monday=0, Sunday=6)
    is_weekday = now.weekday() < 5

    return is_weekday and market_start <= current_time <= market_end
    

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
    market_watch = MarketWatchData(dhan_client)

    # Initialize WebSocket market feed for real-time data
    market_feed = DhanMarketFeed(Config.DHAN_CLIENT_ID, Config.DHAN_ACCESS_TOKEN)
    market_feed.connect()
    market_feed.start()
    logger.info("Real-time market feed WebSocket started")

    # Tracking variables
    last_trade_sync_time = 0.0
    iteration_count = 0

    try:
        logger.info(f"Pipeline active for Expiry: {expiry}")

        while True:
            iteration_count += 1
            current_time = time.time()
            """
            # Check market hours (can be disabled for testing)
            if not is_market_hours() and not Config.DEBUG:
                logger.info("Outside market hours. Waiting 60 seconds...")
                time.sleep(60)
                continue
            """

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

                # --- STEP 3: Fetch and Store Market Watch Data (REST API) ---
                try:
                    instruments_count = market_watch.fetch_and_store()
                    logger.info(f"Market watch: Stored {instruments_count} instruments")
                except MarketWatchError as e:
                    logger.error(f"Market watch fetch failed: {e}")

                # --- STEP 4: Store Real-time Market Feed Data (WebSocket) ---
                try:
                    market_feed.store_to_database()
                    latest_data = market_feed.get_latest_data()
                    logger.info(f"Real-time feed: Stored data for {len(latest_data)} instruments")
                except MarketFeedError as e:
                    logger.error(f"Market feed store failed: {e}")

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