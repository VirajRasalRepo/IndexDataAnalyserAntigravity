"""
Option chain data module.
Handles fetching and storing option chain data from Dhan API.
"""

import logging
from typing import Dict, Tuple, Optional
from dhanhq import dhanhq

from .config import Config, now_ist
from .database import DatabaseManager
from . import Utilities

logger = logging.getLogger(__name__)


class OptionChainError(Exception):
    """Raised when option chain operations fail."""
    pass


class OptionChainData:
    """Handles fetching and storing option chain data."""

    # SQL query for inserting option chain data
    INSERT_OC_QUERY = """
        INSERT INTO nifty_oc_historical
        (Date, Time, Spot_price, Strike_price, ce_oi, ce_volume, ce_IV,
        ce_delta, ce_gamma, ce_theta, ce_price, ce_vega,
        pe_oi, pe_volume, pe_IV, pe_delta, pe_gamma,
        pe_theta, pe_price, pe_vega)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    def __init__(self, dhan_client: dhanhq, expiry: str):
        """
        Initialize OptionChainData.

        Args:
            dhan_client: Initialized Dhan API client
            expiry: Expiry date for option chain (format: YYYY-MM-DD)
        """
        self.dhan_client = dhan_client
        self.expiry = expiry

    def fetch_and_store(self) -> Tuple[int, float]:
        """
        Fetch option chain data from API and store in database.

        Returns:
            Tuple of (number of strikes stored, spot price)

        Raises:
            OptionChainError: If fetch or store operation fails
        """
        try:
            # Fetch option chain data
            response = self.dhan_client.option_chain(
                under_security_id=Config.NIFTY_SECURITY_ID,
                under_exchange_segment=Config.NIFTY_EXCHANGE_SEGMENT,
                expiry=self.expiry
            )

            if response.get('status') != 'success':
                error_msg = response.get('remarks', 'Unknown error')
                raise OptionChainError(f"Dhan API error: {error_msg}")

            # Parse response data
            oc_data, spot_price = self._parse_response(response)

            if not oc_data:
                logger.warning("No option chain data available")
                return 0, spot_price

            # Prepare and insert data
            strikes_stored = self._store_option_data(oc_data, spot_price)

            return strikes_stored, spot_price

        except OptionChainError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in fetch_and_store: {e}", exc_info=True)
            raise OptionChainError(f"Option chain operation failed: {e}") from e

    def _parse_response(self, response: Dict) -> Tuple[Dict, float]:
        """
        Parse API response to extract option chain data and spot price.

        Args:
            response: API response dictionary

        Returns:
            Tuple of (option chain data dict, spot price)
        """
        data_payload = response.get('data', {})
        inner_data = data_payload.get('data', data_payload)
        oc_data = inner_data.get('oc', {})
        spot_price = inner_data.get('last_price', 0.0)

        return oc_data, spot_price

    def _store_option_data(self, oc_data: Dict, spot_price: float) -> int:
        """
        Store option chain data in database.

        Args:
            oc_data: Option chain data dictionary
            spot_price: Current spot price

        Returns:
            Number of strikes stored
        """
        now = now_ist()
        current_date = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M:%S')

        # Calculate ATM strike and range
        atm_strike = Utilities.get_atm_strike(spot_price)
        min_strike = atm_strike - Config.STRIKE_RANGE
        max_strike = atm_strike + Config.STRIKE_RANGE

        # Prepare data for batch insert
        strike_data_list = []

        for strike_str, strike_values in oc_data.items():
            strike_price = float(strike_str)

            # Filter strikes within range
            if not (min_strike <= strike_price <= max_strike):
                continue

            strike_data = self._extract_strike_data(
                strike_values, current_date, current_time, spot_price, strike_price
            )

            if strike_data:
                strike_data_list.append(strike_data)

        # Batch insert
        if strike_data_list:
            with DatabaseManager.get_cursor() as cursor:
                cursor.executemany(self.INSERT_OC_QUERY, strike_data_list)
                return cursor.rowcount

        return 0

    def _extract_strike_data(
        self,
        strike_values: Dict,
        current_date: str,
        current_time: str,
        spot_price: float,
        strike_price: float
    ) -> Optional[Tuple]:
        """
        Extract and validate strike data for database insertion.

        Args:
            strike_values: Strike data from API
            current_date: Current date string
            current_time: Current time string
            spot_price: Spot price
            strike_price: Strike price

        Returns:
            Tuple of strike data or None if invalid
        """
        try:
            call_option = strike_values.get('ce', {})
            put_option = strike_values.get('pe', {})
            call_greeks = call_option.get('greeks', {})
            put_greeks = put_option.get('greeks', {})

            return (
                current_date,
                current_time,
                spot_price,
                strike_price,
                call_option.get('oi', 0),
                call_option.get('volume', 0),
                call_option.get('implied_volatility', 0.0),
                call_greeks.get('delta', 0.0),
                call_greeks.get('gamma', 0.0),
                call_greeks.get('theta', 0.0),
                call_option.get('last_price', 0.0),
                call_greeks.get('vega', 0.0),
                put_option.get('oi', 0),
                put_option.get('volume', 0),
                put_option.get('implied_volatility', 0.0),
                put_greeks.get('delta', 0.0),
                put_greeks.get('gamma', 0.0),
                put_greeks.get('theta', 0.0),
                put_option.get('last_price', 0.0),
                put_greeks.get('vega', 0.0)
            )
        except Exception as e:
            logger.warning(f"Failed to extract strike data for {strike_price}: {e}")
            return None
