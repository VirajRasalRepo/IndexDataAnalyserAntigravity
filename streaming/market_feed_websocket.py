"""
Market Feed WebSocket module.
Handles real-time market data streaming from Dhan WebSocket API.
"""

import json
import logging
import struct
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Callable
import sys
from pathlib import Path
import websocket

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Config
from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class MarketFeedError(Exception):
    """Raised when market feed operations fail."""
    pass


class DhanMarketFeed:
    """Handles real-time market data streaming via WebSocket."""

    # WebSocket URL
    WS_URL = "wss://api-feed.dhan.co"

    # Request codes
    SUBSCRIPTION_CODE = 15  # Subscribe
    UNSUBSCRIPTION_CODE = 16  # Unsubscribe
    QUOTE_MODE = 4  # Quote packet mode

    # Exchange segment codes
    EXCHANGE_SEGMENTS = {
        "IDX_I": 13,
        "NSE_EQ": 1,
        "NSE_FNO": 2,
        "BSE_EQ": 11,
        "BSE_FNO": 12,
    }

    # Market instruments configuration
    INSTRUMENTS = [
        {"security_id": 26017, "exchange_segment": "IDX_I", "prefix": "india_vix"},
        {"security_id": 13, "exchange_segment": "IDX_I", "prefix": "nifty_50"},
        {"security_id": 2885, "exchange_segment": "NSE_EQ", "prefix": "reliance"},
        {"security_id": 1333, "exchange_segment": "NSE_EQ", "prefix": "hdfc_bank"},
        {"security_id": 4963, "exchange_segment": "NSE_EQ", "prefix": "icici_bank"},
        {"security_id": 1594, "exchange_segment": "NSE_EQ", "prefix": "infosys"},
        {"security_id": 11536, "exchange_segment": "NSE_EQ", "prefix": "tcs"},
        {"security_id": 1660, "exchange_segment": "NSE_EQ", "prefix": "itc"},
        {"security_id": 11483, "exchange_segment": "NSE_EQ", "prefix": "lt"},
    ]

    def __init__(self, client_id: str, access_token: str):
        """
        Initialize DhanMarketFeed.

        Args:
            client_id: Dhan client ID
            access_token: Dhan access token
        """
        self.client_id = client_id
        self.access_token = access_token
        self.ws = None
        self.connected = False
        self.running = False
        self.thread = None

        # Store latest market data
        self.market_data: Dict[str, Dict] = {}
        self.data_lock = threading.Lock()

        # Callbacks
        self.on_data_callback: Optional[Callable] = None

    def connect(self) -> None:
        """Establish WebSocket connection."""
        try:
            ws_url = (
                f"{self.WS_URL}?"
                f"version=2&"
                f"token={self.access_token}&"
                f"clientId={self.client_id}&"
                f"authType=2"
            )

            self.ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            logger.info("WebSocket connection initiated")

        except Exception as e:
            logger.error(f"Failed to create WebSocket connection: {e}")
            raise MarketFeedError(f"Connection failed: {e}") from e

    def start(self) -> None:
        """Start WebSocket in background thread."""
        if self.running:
            logger.warning("WebSocket already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_forever, daemon=True)
        self.thread.start()
        logger.info("WebSocket thread started")

    def stop(self) -> None:
        """Stop WebSocket connection."""
        self.running = False
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("WebSocket stopped")

    def _run_forever(self) -> None:
        """Run WebSocket connection with auto-reconnect."""
        while self.running:
            try:
                if self.ws:
                    self.ws.run_forever(ping_interval=10, ping_timeout=5)
                else:
                    self.connect()
                    if self.ws:
                        self.ws.run_forever(ping_interval=10, ping_timeout=5)

                if self.running:
                    logger.warning("WebSocket disconnected. Reconnecting in 5 seconds...")
                    time.sleep(5)

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if self.running:
                    time.sleep(5)

    def _on_open(self, ws) -> None:
        """Called when WebSocket connection is established."""
        logger.info("WebSocket connected successfully")
        self.connected = True

        # Subscribe to all instruments
        self._subscribe_instruments()

    def _on_message(self, ws, message) -> None:
        """
        Called when message is received from WebSocket.

        Args:
            ws: WebSocket instance
            message: Binary message data
        """
        try:
            logger.debug(f"Received message: {len(message)} bytes")

            # Parse binary message
            data = self._parse_quote_packet(message)

            if data:
                # Update market data store
                instrument_key = f"{data['exchange_segment']}_{data['security_id']}"

                with self.data_lock:
                    self.market_data[instrument_key] = data

                # Call callback if registered
                if self.on_data_callback:
                    self.on_data_callback(data)

                logger.info(f"Received data for {instrument_key}: LTP={data.get('ltp', 0)}")
            else:
                logger.warning(f"Failed to parse message of {len(message)} bytes")

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    def _on_error(self, ws, error) -> None:
        """Called when WebSocket error occurs."""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """Called when WebSocket connection is closed."""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False

    def _subscribe_instruments(self) -> None:
        """Subscribe to all configured instruments with Quote mode."""
        try:
            # Prepare instrument list
            instrument_list = []
            for instrument in self.INSTRUMENTS:
                exchange_code = self.EXCHANGE_SEGMENTS.get(instrument["exchange_segment"], 1)
                instrument_list.append({
                    "ExchangeSegment": exchange_code,
                    "SecurityId": str(instrument["security_id"])
                })

            # Create subscription message
            subscription_msg = {
                "RequestCode": self.SUBSCRIPTION_CODE,
                "InstrumentCount": len(instrument_list),
                "InstrumentList": instrument_list
            }

            # Send subscription
            self.ws.send(json.dumps(subscription_msg))
            logger.info(f"Subscribed to {len(instrument_list)} instruments in Quote mode")

        except Exception as e:
            logger.error(f"Failed to subscribe to instruments: {e}")

    def _parse_quote_packet(self, data: bytes) -> Optional[Dict]:
        """
        Parse Quote Packet (Mode 4) binary data.

        Binary format (Little Endian):
        - Header: 8 bytes
        - Exchange Segment: 1 byte
        - Security ID: 4 bytes (int32)
        - LTP: 4 bytes (float32)
        - LTQ: 4 bytes (int32)
        - LTT: 4 bytes (int32) - EPOCH
        - Average Price: 4 bytes (float32)
        - Volume: 4 bytes (int32)
        - Total Buy Qty: 4 bytes (float32)
        - Total Sell Qty: 4 bytes (float32)
        - Open: 4 bytes (float32)
        - High: 4 bytes (float32)
        - Low: 4 bytes (float32)
        - Close: 4 bytes (float32)

        Args:
            data: Binary data from WebSocket

        Returns:
            Dictionary with parsed data or None
        """
        try:
            if len(data) < 52:  # Minimum packet size
                return None

            # Parse header (8 bytes) - skip for now
            offset = 8

            # Parse data fields (Little Endian format)
            exchange_segment = struct.unpack_from('<B', data, offset)[0]
            offset += 1

            security_id = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            ltp = struct.unpack_from('<f', data, offset)[0]
            offset += 4

            ltq = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            ltt_epoch = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            avg_price = struct.unpack_from('<f', data, offset)[0]
            offset += 4

            volume = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            total_buy_qty = struct.unpack_from('<f', data, offset)[0]
            offset += 4

            total_sell_qty = struct.unpack_from('<f', data, offset)[0]
            offset += 4

            open_price = struct.unpack_from('<f', data, offset)[0]
            offset += 4

            high_price = struct.unpack_from('<f', data, offset)[0]
            offset += 4

            low_price = struct.unpack_from('<f', data, offset)[0]
            offset += 4

            close_price = struct.unpack_from('<f', data, offset)[0]

            return {
                'exchange_segment': exchange_segment,
                'security_id': security_id,
                'ltp': round(ltp, 2),
                'ltq': ltq,
                'ltt_epoch': ltt_epoch,
                'avg_price': round(avg_price, 2),
                'volume': volume,
                'total_buy_qty': int(total_buy_qty),
                'total_sell_qty': int(total_sell_qty),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'timestamp': datetime.now()
            }

        except Exception as e:
            logger.error(f"Error parsing quote packet: {e}")
            return None

    def get_latest_data(self) -> Dict:
        """
        Get latest market data for all instruments.

        Returns:
            Dictionary mapping instrument keys to their latest data
        """
        with self.data_lock:
            return self.market_data.copy()

    def store_to_database(self) -> None:
        """Store latest market data to database."""
        try:
            with self.data_lock:
                if not self.market_data:
                    logger.warning("No market data to store")
                    return

                # Prepare data for insertion
                data_dict = {}

                for instrument in self.INSTRUMENTS:
                    key = f"{self.EXCHANGE_SEGMENTS.get(instrument['exchange_segment'])}_{instrument['security_id']}"
                    prefix = instrument['prefix']

                    if key in self.market_data:
                        md = self.market_data[key]
                        data_dict[f"{prefix}_ltp"] = md.get('ltp', 0.0)
                        data_dict[f"{prefix}_volume"] = md.get('volume', 0)
                        data_dict[f"{prefix}_open"] = md.get('open', 0.0)
                        data_dict[f"{prefix}_high"] = md.get('high', 0.0)
                        data_dict[f"{prefix}_low"] = md.get('low', 0.0)
                        data_dict[f"{prefix}_close"] = md.get('close', 0.0)

                        # Only for equity instruments (not indices)
                        if instrument['exchange_segment'] == 'NSE_EQ':
                            data_dict[f"{prefix}_avg_price"] = md.get('avg_price', 0.0)
                            data_dict[f"{prefix}_total_buy_qty"] = md.get('total_buy_qty', 0)
                            data_dict[f"{prefix}_total_sell_qty"] = md.get('total_sell_qty', 0)
                    else:
                        # Set default values if no data
                        data_dict[f"{prefix}_ltp"] = 0.0
                        data_dict[f"{prefix}_volume"] = 0
                        data_dict[f"{prefix}_open"] = 0.0
                        data_dict[f"{prefix}_high"] = 0.0
                        data_dict[f"{prefix}_low"] = 0.0
                        data_dict[f"{prefix}_close"] = 0.0

                        if instrument['exchange_segment'] == 'NSE_EQ':
                            data_dict[f"{prefix}_avg_price"] = 0.0
                            data_dict[f"{prefix}_total_buy_qty"] = 0
                            data_dict[f"{prefix}_total_sell_qty"] = 0

                # Insert into database
                self._insert_market_data(data_dict)

                logger.info(f"Stored market data for {len(self.market_data)} instruments")

        except Exception as e:
            logger.error(f"Failed to store market data: {e}", exc_info=True)

    def _insert_market_data(self, data: Dict) -> None:
        """
        Insert market data into database.

        Args:
            data: Dictionary with all market data fields
        """
        # Build dynamic SQL query
        columns = ['timestamp'] + list(data.keys())
        placeholders = ['NOW(3)'] + ['%s'] * len(data)

        query = f"""
            INSERT INTO market_feed_realtime ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """

        values = tuple(data.values())

        with DatabaseManager.get_cursor() as cursor:
            cursor.execute(query, values)
