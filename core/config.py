"""
Configuration module for Index Data Analyser.
Loads settings from environment variables with validation.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


# IST timezone (UTC+5:30) — used everywhere instead of naive datetime.now()
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Get current time in IST. Use this instead of datetime.now() everywhere."""
    return datetime.now(IST)


class Config:
    """Application configuration loaded from environment variables."""

    # Dhan API Configuration
    DHAN_CLIENT_ID: str = os.getenv("DHAN_CLIENT_ID", "")
    DHAN_ACCESS_TOKEN: str = os.getenv("DHAN_ACCESS_TOKEN", "")

    # Database Configuration
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "analyzer_db")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))

    # Application Settings
    TRADE_SYNC_INTERVAL: int = int(os.getenv("TRADE_SYNC_INTERVAL", "60"))
    DATA_FETCH_INTERVAL: int = int(os.getenv("DATA_FETCH_INTERVAL", "4"))
    STRIKE_RANGE: int = int(os.getenv("STRIKE_RANGE", "750"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Market Hours (IST)
    MARKET_START_HOUR: int = 9
    MARKET_START_MINUTE: int = 15
    MARKET_END_HOUR: int = 15
    MARKET_END_MINUTE: int = 30

    # Market Holidays - Fetched dynamically from NSE API (cached daily)
    # Falls back to hardcoded list if NSE is unreachable
    MARKET_HOLIDAYS = []  # Populated at module load via _load_holidays()

    @classmethod
    def _load_holidays(cls):
        """Load market holidays from NSE API (with caching and fallback)."""
        try:
            from .Utilities import fetch_market_holidays
            cls.MARKET_HOLIDAYS = fetch_market_holidays()
            logger.info(f"Loaded {len(cls.MARKET_HOLIDAYS)} market holidays")
        except Exception as e:
            logger.warning(f"Failed to load holidays dynamically: {e}")
            cls.MARKET_HOLIDAYS = [
                "2025-01-26", "2025-03-14", "2025-08-15", "2025-10-02", "2025-12-25",
                "2026-01-26", "2026-03-03", "2026-08-15", "2026-10-02", "2026-12-25",
            ]

    # Nifty Option Chain Constants
    NIFTY_SECURITY_ID: int = 13
    NIFTY_EXCHANGE_SEGMENT: str = "IDX_I"

    # Greeks Configuration (DEPRECATED - Auto-detected from Dhan API)
    # NIFTY weekly expiry is every TUESDAY (not Thursday)
    # Expiry is auto-fetched from Dhan API - no manual updates needed
    ACTIVE_EXPIRY: str = os.getenv("ACTIVE_EXPIRY", "")  # Deprecated - kept for backward compatibility

    @classmethod
    def reload_credentials(cls) -> bool:
        """
        Re-read DHAN credentials from .env file.
        Returns True if credentials changed, False otherwise.
        """
        load_dotenv(override=True)
        new_client_id = os.getenv("DHAN_CLIENT_ID", "")
        new_access_token = os.getenv("DHAN_ACCESS_TOKEN", "")

        if new_client_id != cls.DHAN_CLIENT_ID or new_access_token != cls.DHAN_ACCESS_TOKEN:
            cls.DHAN_CLIENT_ID = new_client_id
            cls.DHAN_ACCESS_TOKEN = new_access_token
            logger.info("Dhan API credentials reloaded from .env")
            return True
        return False

    @classmethod
    def get_db_config(cls) -> Dict[str, Any]:
        """Returns database configuration as a dictionary."""
        return {
            "host": cls.DB_HOST,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
            "database": cls.DB_NAME,
            "port": cls.DB_PORT
        }

    @classmethod
    def validate(cls) -> None:
        """
        Validates that all required configuration values are present.

        Raises:
            ConfigurationError: If required configuration is missing.
        """
        missing_configs = []

        if not cls.DHAN_CLIENT_ID:
            missing_configs.append("DHAN_CLIENT_ID")

        if not cls.DHAN_ACCESS_TOKEN:
            missing_configs.append("DHAN_ACCESS_TOKEN")

        if not cls.DB_PASSWORD:
            logger.warning("DB_PASSWORD is not set. Using empty password.")

        if missing_configs:
            raise ConfigurationError(
                f"Missing required configuration: {', '.join(missing_configs)}. "
                "Please check your .env file."
            )

        logger.info("Configuration validated successfully")


# Validate configuration on module import
try:
    Config.validate()
except ConfigurationError as e:
    logger.error(f"Configuration error: {e}")
    raise

# Load market holidays from NSE API (with caching)
Config._load_holidays()
