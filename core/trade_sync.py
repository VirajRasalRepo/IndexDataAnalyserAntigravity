"""
Trade synchronization module.
Handles fetching and storing trade data from Dhan API to database.
"""

import logging
from typing import Dict, Set
from dhanhq import dhanhq

from .database import DatabaseManager

logger = logging.getLogger(__name__)


class TradeSyncError(Exception):
    """Raised when trade synchronization fails."""
    pass


class TradeSync:
    """Handles synchronization of trades from Dhan API to database."""

    # SQL query for inserting trades (INSERT IGNORE to skip duplicates)
    INSERT_TRADE_QUERY = """
        INSERT IGNORE INTO USER_TRADES
        (trade_id, order_id, symbol, transaction_type, quantity,
         entry_price, entry_time, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    def __init__(self, dhan_client: dhanhq):
        """
        Initialize TradeSync.

        Args:
            dhan_client: Initialized Dhan API client
        """
        self.dhan_client = dhan_client
        self._seen_order_ids: Set[str] = set()

    def sync_trades(self) -> int:
        """
        Fetch trades from Dhan API and sync to database.

        Returns:
            Number of new trades synced

        Raises:
            TradeSyncError: If synchronization fails
        """
        try:
            response = self.dhan_client.get_trade_book()

            if response.get('status') != 'success':
                error_msg = response.get('remarks', 'Unknown error')
                raise TradeSyncError(f"Dhan API error: {error_msg}")

            all_trades = response.get('data', [])

            if not all_trades:
                logger.debug("No trades to sync")
                return 0

            # Filter and prepare trade data
            trade_data_list = self._prepare_trade_data(all_trades)

            if not trade_data_list:
                logger.debug("No new trades after filtering duplicates")
                return 0

            # Batch insert trades
            new_count = self._insert_trades(trade_data_list)

            logger.info(f"Successfully synced {new_count} new trades")
            return new_count

        except TradeSyncError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during trade sync: {e}", exc_info=True)
            raise TradeSyncError(f"Trade sync failed: {e}") from e

    def _prepare_trade_data(self, all_trades: list) -> list:
        """
        Prepare and validate trade data for database insertion.

        Args:
            all_trades: List of trade dictionaries from API

        Returns:
            List of tuples ready for database insertion
        """
        trade_data_list = []
        current_batch_order_ids = set()

        for trade in all_trades:
            order_id = str(trade.get('orderId', ''))

            # Skip if already processed in this batch
            if order_id in current_batch_order_ids:
                logger.debug(f"Duplicate order_id in batch: {order_id}")
                continue

            # Validate required fields
            if not self._validate_trade(trade):
                logger.warning(f"Invalid trade data: {trade}")
                continue

            trade_data = (
                str(trade.get('exchangeTradeId', '')),  # Fixed: use exchangeTradeId
                order_id,
                trade.get('tradingSymbol', ''),
                trade.get('transactionType', ''),
                trade.get('tradedQuantity', 0),
                trade.get('tradedPrice', 0.0),
                trade.get('createTime', ''),
                trade.get('productType', '')  # Fixed: use productType instead of orderStatus
            )

            trade_data_list.append(trade_data)
            current_batch_order_ids.add(order_id)

        return trade_data_list

    def _validate_trade(self, trade: Dict) -> bool:
        """
        Validate that trade has required fields.

        Args:
            trade: Trade dictionary from API

        Returns:
            True if valid, False otherwise
        """
        required_fields = ['exchangeTradeId', 'orderId', 'tradingSymbol', 'transactionType']
        return all(trade.get(field) is not None for field in required_fields)

    def _insert_trades(self, trade_data_list: list) -> int:
        """
        Insert trades into database using batch insert.

        Args:
            trade_data_list: List of trade data tuples

        Returns:
            Number of rows inserted
        """
        try:
            with DatabaseManager.get_cursor() as cursor:
                cursor.executemany(self.INSERT_TRADE_QUERY, trade_data_list)
                return cursor.rowcount

        except Exception as e:
            logger.error(f"Failed to insert trades: {e}")
            raise TradeSyncError(f"Database insert failed: {e}") from e

    def clear_seen_orders(self) -> None:
        """Clear the set of seen order IDs (useful for testing or reset)."""
        self._seen_order_ids.clear()
        logger.debug("Cleared seen order IDs")
