"""
Test WebSocket Connection
Quick test to verify if WebSocket is working and receiving data
"""

import logging
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import Config
from streaming.market_feed_websocket import DhanMarketFeed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_websocket():
    """Test WebSocket connection and data reception."""

    print("=" * 60)
    print("WebSocket Connection Test")
    print("=" * 60)
    print()

    # Check credentials
    if not Config.DHAN_CLIENT_ID or not Config.DHAN_ACCESS_TOKEN:
        print("[ERROR] DHAN credentials not configured in .env file")
        print("        Please set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN")
        return False

    print(f"[OK] Client ID: {Config.DHAN_CLIENT_ID[:10]}...")
    print(f"[OK] Access Token: {Config.DHAN_ACCESS_TOKEN[:10]}...")
    print()

    try:
        # Initialize WebSocket
        print("Initializing WebSocket...")
        market_feed = DhanMarketFeed(Config.DHAN_CLIENT_ID, Config.DHAN_ACCESS_TOKEN)

        # Connect
        print("Connecting to: wss://api-feed.dhan.co")
        market_feed.connect()

        # Start
        print("Starting WebSocket...")
        market_feed.start()

        print("[OK] WebSocket started")
        print()
        print("Waiting for data (30 seconds)...")
        print("Press Ctrl+C to stop early")
        print()

        # Wait and check for data
        for i in range(30):
            time.sleep(1)

            if market_feed.connected:
                data = market_feed.get_latest_data()

                if i % 5 == 0:  # Print every 5 seconds
                    print(f"[{i}s] Connected: YES | Instruments: {len(data)}")

                    if data:
                        print("\nSample data:")
                        for key, value in list(data.items())[:3]:  # Show first 3
                            print(f"  {key}: LTP={value.get('ltp', 0)}, Vol={value.get('volume', 0)}")
                        print()
            else:
                print(f"[{i}s] Not connected yet...")

        # Final status
        print()
        print("=" * 60)
        print("Test Results")
        print("=" * 60)

        if market_feed.connected:
            print("[OK] Connection Status: CONNECTED")
        else:
            print("[FAIL] Connection Status: NOT CONNECTED")

        final_data = market_feed.get_latest_data()
        print(f"[OK] Instruments Received: {len(final_data)}")

        if final_data:
            print("\n[SUCCESS] WebSocket is WORKING!")
            print("\nReceived data for:")
            for key in final_data.keys():
                print(f"  - {key}")
        else:
            print("\n[WARNING] WebSocket connected but NO DATA received")
            print("  This might be because:")
            print("  1. Market is closed (currently outside 9:15 AM - 3:30 PM IST)")
            print("  2. No market activity")
            print("  3. Subscription failed")

        # Stop
        print("\nStopping WebSocket...")
        market_feed.stop()
        print("[OK] Stopped")

        return len(final_data) > 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        logger.error("WebSocket test failed", exc_info=True)
        return False

if __name__ == "__main__":
    try:
        success = test_websocket()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
