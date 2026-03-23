"""
Utility functions for Index Data Analyser.
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger(__name__)

# IST timezone (inline to avoid circular import with config.py)
_IST = timezone(timedelta(hours=5, minutes=30))

# Path to cached holidays file (project root)
_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "holidays_cache.json")

# Minimal fallback holidays if NSE API and cache both fail
_FALLBACK_HOLIDAYS = [
    "2025-01-26", "2025-03-14", "2025-08-15", "2025-10-02", "2025-12-25",
    "2026-01-26", "2026-03-03", "2026-08-15", "2026-10-02", "2026-12-25",
    "2027-01-26", "2027-08-15", "2027-10-02", "2027-12-25",
]


def _load_cache():
    """Load holidays from cache file if it exists and is fresh (today)."""
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, "r") as f:
                cache = json.load(f)
            if cache.get("fetched_date") == datetime.now(_IST).strftime("%Y-%m-%d"):
                return cache.get("holidays", [])
            # Return stale cache data (will be used as fallback)
            return cache.get("holidays", [])
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read holiday cache: {e}")
    return None


def _is_cache_fresh():
    """Check if cache was fetched today."""
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, "r") as f:
                cache = json.load(f)
            return cache.get("fetched_date") == datetime.now(_IST).strftime("%Y-%m-%d")
    except (json.JSONDecodeError, OSError):
        pass
    return False


def _save_cache(holidays):
    """Save holidays list to cache file."""
    try:
        cache = {
            "fetched_date": datetime.now(_IST).strftime("%Y-%m-%d"),
            "holidays": holidays,
        }
        with open(_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
        logger.info(f"Holiday cache saved with {len(holidays)} holidays")
    except OSError as e:
        logger.warning(f"Failed to save holiday cache: {e}")


def _fetch_from_nse():
    """Fetch trading holidays from NSE website API."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })

    # First hit the homepage to get session cookies
    session.get("https://www.nseindia.com", timeout=10)

    # Now fetch holidays
    response = session.get(
        "https://www.nseindia.com/api/holiday-master?type=trading",
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    holidays = set()
    # NSE API returns holidays grouped by market segment (CM, FO, CD, etc.)
    for segment_key in data:
        segment_holidays = data[segment_key]
        if isinstance(segment_holidays, list):
            for entry in segment_holidays:
                raw_date = entry.get("tradingDate", "")
                if raw_date:
                    try:
                        parsed = datetime.strptime(raw_date, "%d-%b-%Y")
                        holidays.add(parsed.strftime("%Y-%m-%d"))
                    except ValueError:
                        continue

    return sorted(holidays)


def fetch_market_holidays():
    """
    Get market holidays list. Tries NSE API with daily caching,
    falls back to stale cache or hardcoded list on failure.

    Returns:
        List of holiday date strings in YYYY-MM-DD format.
    """
    # If cache is fresh (fetched today), use it directly
    if _is_cache_fresh():
        cached = _load_cache()
        if cached:
            logger.info(f"Using cached holidays ({len(cached)} dates)")
            return cached

    # Try fetching from NSE
    try:
        holidays = _fetch_from_nse()
        if holidays:
            _save_cache(holidays)
            logger.info(f"Fetched {len(holidays)} holidays from NSE")
            return holidays
    except Exception as e:
        logger.warning(f"Failed to fetch holidays from NSE: {e}")

    # Fall back to stale cache
    stale = _load_cache()
    if stale:
        logger.warning(f"Using stale cached holidays ({len(stale)} dates)")
        return stale

    # Last resort: hardcoded fallback
    logger.warning("Using hardcoded fallback holidays")
    return _FALLBACK_HOLIDAYS


def get_atm_strike(last_price, base=50):
    """Calculate ATM strike price rounded to nearest base."""
    return base * round(last_price / base)


def get_expiry_list(dhan):
    """
    Fetch next available expiry date from Dhan API.
    Returns the nearest expiry date string (YYYY-MM-DD).
    """
    logger.info("Fetching valid expiries for Nifty 50...")
    try:
        expiry_response = dhan.expiry_list(under_security_id=13, under_exchange_segment="IDX_I")

        if expiry_response.get('status') == 'success':
            next_expiry = expiry_response['data']['data'][0]
            logger.info(f"Targeting Expiry: {next_expiry}")
            return next_expiry
        else:
            logger.warning(f"Expiry list fetch failed: {expiry_response.get('remarks', 'Unknown error')}")
            return None
    except Exception as e:
        logger.error(f"Error fetching expiry list: {e}")
        return None
