"""
Configuration module for Index Data Analyser.
Loads settings from environment variables with validation.
"""

import os
import logging
from typing import Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


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

    # Market Holidays (YYYY-MM-DD format)
    # Indian Stock Market Holidays - Updated annually
    MARKET_HOLIDAYS = [
        # 2025 Holidays
        "2025-01-26",  # Republic Day
        "2025-03-14",  # Holi
        "2025-03-31",  # Id-Ul-Fitr (Ramadan Eid)
        "2025-04-10",  # Mahavir Jayanti
        "2025-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
        "2025-04-18",  # Good Friday
        "2025-05-01",  # Maharashtra Day
        "2025-06-07",  # Id-Ul-Adha (Bakri Eid)
        "2025-07-06",  # Muharram
        "2025-08-15",  # Independence Day
        "2025-08-27",  # Ganesh Chaturthi
        "2025-10-02",  # Mahatma Gandhi Jayanti
        "2025-10-21",  # Dussehra
        "2025-11-05",  # Diwali (Laxmi Pujan)
        "2025-11-06",  # Diwali (Balipratipada)
        "2025-11-24",  # Guru Nanak Jayanti
        "2025-12-25",  # Christmas

        # 2026 Holidays (to be updated with official NSE calendar)
        "2026-01-26",  # Republic Day
        "2026-03-03",  # Holi
        "2026-03-20",  # Id-Ul-Fitr (Ramadan Eid)
        "2026-03-30",  # Mahavir Jayanti
        "2026-04-03",  # Good Friday
        "2026-04-06",  # Shri Ram Navami
        "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
        "2026-05-01",  # Maharashtra Day
        "2026-05-27",  # Id-Ul-Adha (Bakri Eid)
        "2026-06-16",  # Muharram
        "2026-08-15",  # Independence Day
        "2026-09-16",  # Ganesh Chaturthi
        "2026-10-02",  # Mahatma Gandhi Jayanti
        "2026-10-10",  # Dussehra
        "2026-10-25",  # Diwali (Laxmi Pujan)
        "2026-10-26",  # Diwali (Balipratipada)
        "2026-11-13",  # Guru Nanak Jayanti
        "2026-12-25",  # Christmas

        # 2027 Holidays (tentative - to be updated)
        "2027-01-26",  # Republic Day
        "2027-03-10",  # Id-Ul-Fitr (Ramadan Eid)
        "2027-03-25",  # Holi
        "2027-04-02",  # Good Friday
        "2027-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
        "2027-05-17",  # Id-Ul-Adha (Bakri Eid)
        "2027-06-06",  # Muharram
        "2027-08-15",  # Independence Day
        "2027-09-06",  # Ganesh Chaturthi
        "2027-10-02",  # Mahatma Gandhi Jayanti
        "2027-10-30",  # Dussehra
        "2027-11-14",  # Diwali (Laxmi Pujan)
        "2027-11-15",  # Diwali (Balipratipada)
        "2027-12-03",  # Guru Nanak Jayanti
        "2027-12-25",  # Christmas
    ]

    # Nifty Option Chain Constants
    NIFTY_SECURITY_ID: int = 13
    NIFTY_EXCHANGE_SEGMENT: str = "IDX_I"

    # Greeks Configuration (DEPRECATED - Auto-detected from Dhan API)
    # NIFTY weekly expiry is every TUESDAY (not Thursday)
    # Expiry is auto-fetched from Dhan API - no manual updates needed
    ACTIVE_EXPIRY: str = os.getenv("ACTIVE_EXPIRY", "")  # Deprecated - kept for backward compatibility

    @classmethod
    def get_db_config(cls) -> Dict[str, any]:
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
