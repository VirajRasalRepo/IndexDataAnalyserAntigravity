"""
Market Watch module.
Handles fetching and storing market watch data (OHLC) from Dhan API.
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dhanhq import dhanhq

from database import DatabaseManager

logger = logging.getLogger(__name__)


class MarketWatchError(Exception):
    """Raised when market watch operations fail."""
    pass


class MarketWatchData:
    """Handles fetching and storing market watch OHLC data."""

    # Market instruments configuration
    INSTRUMENTS = [
        {"security_id": "26017", "exchange_segment": "IDX_I", "field_name": "india_vix"},
        {"security_id": "13", "exchange_segment": "IDX_I", "field_name": "nifty_50"},
        {"security_id": "2885", "exchange_segment": "NSE_EQ", "field_name": "reliance_n9_5_s11_5"},
        {"security_id": "1333", "exchange_segment": "NSE_EQ", "field_name": "hdfc_bank_n10_s12"},
        {"security_id": "4963", "exchange_segment": "NSE_EQ", "field_name": "icici_bank_n7_5_s9"},
        {"security_id": "1594", "exchange_segment": "NSE_EQ", "field_name": "infosys_n5_5_s6_5"},
        {"security_id": "11536", "exchange_segment": "NSE_EQ", "field_name": "tcs_n4_s4_8"},
        {"security_id": "1660", "exchange_segment": "NSE_EQ", "field_name": "itc_n4_5_s5"},
        {"security_id": "11483", "exchange_segment": "NSE_EQ", "field_name": "lAt_n3_8_s4_2"},
    ]

    # SQL query for inserting market watch data
    INSERT_QUERY = """
        INSERT INTO market_watch_wide
        (timestamp, india_vix, nifty_50, reliance_n9_5_s11_5, hdfc_bank_n10_s12, icici_bank_n7_5_s9,
         infosys_n5_5_s6_5, tcs_n4_s4_8, itc_n4_5_s5, lAt_n3_8_s4_2)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    def __init__(self, dhan_client: dhanhq):
        """
        Initialize MarketWatchData.

        Args:
            dhan_client: Initialized Dhan API client
        """
        self.dhan_client = dhan_client

    def fetch_and_store(self) -> int:
        """
        Fetch OHLC data for all instruments and store in database.

        Returns:
            Number of instruments stored (1 row with all instruments)

        Raises:
            MarketWatchError: If fetch or store operation fails
        """
        try:
            # Fetch OHLC data for all instruments
            instruments_data = self._fetch_ohlc_data()

            if not instruments_data:
                logger.warning("No market watch data available")
                return 0

            # Store data in database
            self._store_market_data(instruments_data)

            return len(instruments_data)

        except MarketWatchError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in fetch_and_store: {e}", exc_info=True)
            raise MarketWatchError(f"Market watch operation failed: {e}") from e

    def _fetch_ohlc_data(self) -> Dict[str, float]:
        """
        Fetch OHLC data for all configured instruments.

        Returns:
            Dictionary mapping field names to last prices

        Raises:
            MarketWatchError: If API call fails
        """
        instruments_data = {}

        for instrument in self.INSTRUMENTS:
            try:
                # Fetch OHLC data - pass as 'securities' parameter
                response = self.dhan_client.ohlc_data(
                    securities={
                        "security_id": instrument["security_id"],
                        "exchange_segment": instrument["exchange_segment"]
                    }
                )

                if response.get('status') == 'success':
                    data = response.get('data', {})

                    # Handle different response formats
                    if isinstance(data, dict):
                        # Data is a dict with OHLC values
                        last_price = data.get('last_price', data.get('close', 0.0))
                    elif isinstance(data, list) and len(data) > 0:
                        # Data is a list with OHLC values
                        last_price = data[0].get('last_price', data[0].get('close', 0.0))
                    else:
                        last_price = 0.0

                    instruments_data[instrument["field_name"]] = last_price

                    logger.debug(
                        f"{instrument['field_name']}: {last_price} "
                        f"(ID: {instrument['security_id']})"
                    )
                else:
                    error_msg = response.get('remarks', 'Unknown error')
                    logger.warning(
                        f"Failed to fetch {instrument['field_name']}: {error_msg}"
                    )
                    instruments_data[instrument["field_name"]] = 0.0

            except Exception as e:
                logger.error(
                    f"Error fetching {instrument['field_name']}: {e}",
                    exc_info=True
                )
                instruments_data[instrument["field_name"]] = 0.0

        return instruments_data

    def _store_market_data(self, instruments_data: Dict[str, float]) -> None:
        """
        Store market watch data in database.

        Args:
            instruments_data: Dictionary mapping field names to prices

        Raises:
            MarketWatchError: If database insert fails
        """
        try:
            current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Prepare data tuple in correct column order
            data_tuple = (
                current_timestamp,
                instruments_data.get('india_vix', 0.0),
                instruments_data.get('nifty_50', 0.0),
                instruments_data.get('reliance_n9_5_s11_5', 0.0),
                instruments_data.get('hdfc_bank_n10_s12', 0.0),
                instruments_data.get('icici_bank_n7_5_s9', 0.0),
                instruments_data.get('infosys_n5_5_s6_5', 0.0),
                instruments_data.get('tcs_n4_s4_8', 0.0),
                instruments_data.get('itc_n4_5_s5', 0.0),
                instruments_data.get('lAt_n3_8_s4_2', 0.0)
            )

            # Insert into database
            with DatabaseManager.get_cursor() as cursor:
                cursor.execute(self.INSERT_QUERY, data_tuple)

            logger.debug(f"Market watch data stored: {len(instruments_data)} instruments")

        except Exception as e:
            logger.error(f"Failed to store market watch data: {e}")
            raise MarketWatchError(f"Database insert failed: {e}") from e

    def get_current_prices(self) -> Dict[str, float]:
        """
        Fetch current prices without storing (useful for monitoring).

        Returns:
            Dictionary mapping field names to last prices
        """
        try:
            return self._fetch_ohlc_data()
        except Exception as e:
            logger.error(f"Failed to fetch current prices: {e}")
            return {}
