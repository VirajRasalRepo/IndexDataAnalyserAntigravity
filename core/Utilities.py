"""
Utility functions for Index Data Analyser.
"""

import logging

logger = logging.getLogger(__name__)


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
