"""Configuration management for FX Data Pipeline"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration"""

    # OANDA API
    OANDA_API_KEY = os.getenv("OANDA_API_KEY")
    OANDA_BASE_URL_DEMO = "https://api-fxpractice.oanda.com"
    OANDA_BASE_URL_LIVE = "https://api-fxtrade.oanda.com"
    OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT", "demo")  # 'demo' or 'live'

    # Database (supports both DB_* and POSTGRES_* env var names)
    DB_HOST = os.getenv("DB_HOST") or os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT") or os.getenv("POSTGRES_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME") or os.getenv("POSTGRES_DB", "fx_trading_data")
    DB_USER = os.getenv("DB_USER") or os.getenv("POSTGRES_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD", "")

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

    # API Server
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "5000"))
    API_DEBUG = os.getenv("API_DEBUG", "False").lower() == "true"

    # WebSocket
    WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "0.0.0.0")
    WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", "5001"))

    # Tracked instruments by asset class
    FX_TRACKED = [
        "AUD_CHF",
        "AUD_JPY",
        "AUD_USD",
        "CAD_CHF",
        "CAD_JPY",
        "CHF_JPY",
        "EUR_AUD",
        "EUR_CAD",
        "EUR_CHF",
        "EUR_GBP",
        "EUR_JPY",
        "EUR_NZD",
        "EUR_USD",
        "GBP_AUD",
        "GBP_CAD",
        "GBP_CHF",
        "GBP_JPY",
        "GBP_NZD",
        "GBP_USD",
    ]

    METAL_TRACKED = [
        "XAU_USD",
        "XAG_USD",
    ]

    CFD_TRACKED = [
        # US indices
        "US500",
        "US30",
        "USTEC",
        "US2000",
        # Europe indices
        "DE30",
        "FR40",
        "ES35",
        "UK100",
        "STOXX50",
        "SWI20",
        # Asia / Australia indices
        "JP225",
        "AU200",
        # Energy
        "USOIL",
        "UKOIL",
        "NGAS",
    ]

    TRACKED_ALL = FX_TRACKED + METAL_TRACKED + CFD_TRACKED

    CORRELATION_ASSET_CLASSES = {"FX", "METAL"}
    ASSET_CLASS_BY_INSTRUMENT = {
        **{i: "FX" for i in FX_TRACKED},
        **{i: "METAL" for i in METAL_TRACKED},
        **{i: "CFD" for i in CFD_TRACKED},
    }

    # Backward compatibility: legacy tracked pairs map to correlation universe (set after class definition)
    TRACKED_PAIRS = []

    # Cron job settings
    HOURLY_JOB_ENABLED = os.getenv("HOURLY_JOB_ENABLED", "True").lower() == "true"
    DAILY_JOB_ENABLED = os.getenv("DAILY_JOB_ENABLED", "True").lower() == "true"
    HOURLY_JOB_HOUR = "*"  # Every hour
    DAILY_JOB_HOUR = 0  # Midnight UTC
    DAILY_JOB_MINUTE = 0

    # Data retention
    DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "365"))  # 1 year
    PRICE_AUDIT_RETENTION_HOURS = int(os.getenv("PRICE_AUDIT_RETENTION_HOURS", "24"))  # 24 hours

    # Correlation settings
    CORRELATION_THRESHOLD = float(os.getenv("CORRELATION_THRESHOLD", "0.7"))
    CORRELATION_WINDOW_SIZE = int(os.getenv("CORRELATION_WINDOW_SIZE", "100"))

    # Cache settings
    CACHE_TTL_METRICS = int(os.getenv("CACHE_TTL_METRICS", "3600"))  # 1 hour
    CACHE_TTL_PRICES = int(os.getenv("CACHE_TTL_PRICES", "300"))  # 5 minutes
    CACHE_TTL_CORRELATION = int(os.getenv("CACHE_TTL_CORRELATION", "86400"))  # 1 day

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")

    # Rate limiting
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

    # WebSocket settings
    WEBSOCKET_MAX_CLIENTS = int(os.getenv("WEBSOCKET_MAX_CLIENTS", "1000"))
    WEBSOCKET_PING_INTERVAL = int(os.getenv("WEBSOCKET_PING_INTERVAL", "25"))  # seconds
    WEBSOCKET_PING_TIMEOUT = int(os.getenv("WEBSOCKET_PING_TIMEOUT", "5"))  # seconds

    @staticmethod
    def validate():
        """Validate required configuration"""
        required = ["OANDA_API_KEY"]

        missing = [key for key in required if not getattr(Config, key)]

        if missing:
            raise ValueError(f"❌ Missing required environment variables: {', '.join(missing)}")

        print("✅ Configuration validated")


# Validate on import
try:
    Config.validate()
except ValueError as e:
    print(f"⚠️ {e}")

# Finalize TRACKED_PAIRS after class definition
Config.TRACKED_PAIRS = [i for i, cls in Config.ASSET_CLASS_BY_INSTRUMENT.items() if cls in Config.CORRELATION_ASSET_CLASSES]
