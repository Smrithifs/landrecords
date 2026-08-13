"""
Application settings and configuration.
Centralized configuration management using environment variables.
"""

import os
from typing import Dict, Any, List
from pathlib import Path


def _get_proxy_list() -> List[Dict[str, Any]]:
    """
    Get proxy list from environment variable or file.
    
    Returns:
        List of proxy dictionaries
    """
    proxy_list = []
    
    # Try to get from environment variable
    proxies_env = os.getenv("PROXY_LIST", "")
    if proxies_env:
        for proxy_str in proxies_env.split(","):
            parts = proxy_str.strip().split(":")
            if len(parts) >= 2:
                proxy_list.append({
                    "host": parts[0],
                    "port": int(parts[1]),
                    "username": parts[2] if len(parts) > 2 else None,
                    "password": parts[3] if len(parts) > 3 else None
                })
    
    return proxy_list


class Settings:
    """Application settings class."""
    
    # Base paths
    BASE_DIR = Path(__file__).resolve().parent.parent
    PROJECT_ROOT = BASE_DIR
    
    # Application
    APP_NAME = "Bengaluru Land Verification System"
    APP_VERSION = "1.0.0"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Geographic Scope (Extensible for future Karnataka expansion)
    SUPPORTED_DISTRICTS = [
        "Bengaluru Urban",
        "Bengaluru Rural"
    ]
    
    SUPPORTED_PORTALS = [
        "Bhoomi",
        "Kaveri",
        "BBMP",
        "BESCOM",
        "BWSSB",
        "eCourts",
        "KarnatakaHC"
    ]
    
    DEFAULT_DISTRICT = "Bengaluru Urban"
    REGION_SCOPE = "Bengaluru"  # Can be expanded to "Karnataka" in future
    
    # Database Configuration
    DATABASE = {
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": int(os.getenv("DB_PORT", "5432")),
        "db_name": os.getenv("DB_NAME", "land_records"),
        "db_user": os.getenv("DB_USER", "postgres"),
        "db_password": os.getenv("DB_PASSWORD", ""),
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "echo_sql": DEBUG
    }
    
    # Redis Configuration
    REDIS = {
        "redis_host": os.getenv("REDIS_HOST", "localhost"),
        "redis_port": int(os.getenv("REDIS_PORT", "6379")),
        "redis_db": int(os.getenv("REDIS_DB", "0")),
        "redis_password": os.getenv("REDIS_PASSWORD", None),
        "default_ttl": int(os.getenv("REDIS_DEFAULT_TTL", "3600"))
    }
    
    # Scraper Configuration
    SCRAPER = {
        "headless": os.getenv("SCRAPER_HEADLESS", "true").lower() == "true",
        "timeout": int(os.getenv("SCRAPER_TIMEOUT", "30")),
        "page_load_timeout": int(os.getenv("PAGE_LOAD_TIMEOUT", "60")),
        "user_agent": os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ),
        "max_retries": int(os.getenv("MAX_RETRIES", "3")),
        "retry_delay": int(os.getenv("RETRY_DELAY", "2"))
    }
    
    # Portal URLs (Bengaluru-specific)
    PORTALS = {
        "bhoomi_url": os.getenv(
            "BHOOMI_URL",
            "https://landrecords.karnataka.gov.in"
        ),
        "bhoomi_citizen_portal": os.getenv(
            "BHOOMI_CITIZEN_PORTAL",
            "https://landrecords.karnataka.gov.in/citizenportal"
        ),
        "bhoomi_rtc_service": os.getenv(
            "BHOOMI_RTC_SERVICE",
            "https://rtc.karnataka.gov.in/Service78"
        ),
        "kaveri_url": os.getenv(
            "KAVERI_URL",
            "https://kaveri.karnataka.gov.in"
        ),
        "bbmp_url": os.getenv(
            "BBMP_URL",
            "https://bbmp.gov.in"
        ),
        "bescom_url": os.getenv(
            "BESCOM_URL",
            "https://bescom.org"
        ),
        "bwssb_url": os.getenv(
            "BWSSB_URL",
            "https://bwssb.gov.in"
        ),
        "ecourts_url": os.getenv(
            "ECOURTS_URL",
            "https://ecourts.gov.in/ecourts_home.php"
        ),
        "karnataka_hc_url": os.getenv(
            "KARNATAKA_HC_URL",
            "https://judiciary.karnataka.gov.in/casemenu.php"
        )
    }
    
    # Bhoomi Authentication Configuration
    BHOOMI_AUTH = {
        "enabled": os.getenv("BHOOMI_AUTH_ENABLED", "true").lower() == "true",
        "method": os.getenv("BHOOMI_AUTH_METHOD", "citizen_portal"),  # citizen_portal or guest
        "username": os.getenv("BHOOMI_USERNAME", ""),
        "password": os.getenv("BHOOMI_PASSWORD", ""),
        "mobile": os.getenv("BHOOMI_MOBILE", ""),
        "email": os.getenv("BHOOMI_EMAIL", ""),
        "aadhaar": os.getenv("BHOOMI_AADHAAR", ""),
        "session_timeout": int(os.getenv("BHOOMI_SESSION_TIMEOUT", "1800")),  # 30 minutes
        "auto_renew": os.getenv("BHOOMI_AUTO_RENEW", "true").lower() == "true"
    }
    
    # Captcha Service Configuration
    CAPTCHA = {
        "captcha_api_key": os.getenv("CAPTCHA_API_KEY", ""),
        "captcha_service_url": os.getenv("CAPTCHA_SERVICE_URL", ""),
        "captcha_timeout": int(os.getenv("CAPTCHA_TIMEOUT", "120")),
        "enabled": os.getenv("CAPTCHA_ENABLED", "true").lower() == "true"
    }
    
    # Proxy Configuration
    PROXY = {
        "enabled": os.getenv("PROXY_ENABLED", "false").lower() == "true",
        "proxy_list": _get_proxy_list(),
        "max_proxy_failures": int(os.getenv("MAX_PROXY_FAILURES", "3")),
        "rotation_interval": int(os.getenv("PROXY_ROTATION_INTERVAL", "300"))
    }
    
    # Logging Configuration
    LOGGING = {
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "console_level": os.getenv("CONSOLE_LOG_LEVEL", "INFO"),
        "file_level": os.getenv("FILE_LOG_LEVEL", "DEBUG"),
        "log_dir": os.getenv("LOG_DIR", str(BASE_DIR / "logs")),
        "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
    
    # Rate Limiting
    RATE_LIMITING = {
        "enabled": os.getenv("RATE_LIMITING_ENABLED", "true").lower() == "true",
        "requests_per_minute": int(os.getenv("REQUESTS_PER_MINUTE", "30")),
        "requests_per_hour": int(os.getenv("REQUESTS_PER_HOUR", "500"))
    }
    
    # Cache Configuration
    CACHE = {
        "enabled": os.getenv("CACHE_ENABLED", "true").lower() == "true",
        "land_record_ttl": int(os.getenv("LAND_RECORD_TTL", "86400")),  # 24 hours
        "session_ttl": int(os.getenv("SESSION_TTL", "1800")),  # 30 minutes
    }
    
    # Async Configuration
    ASYNC = {
        "max_concurrent_scrapers": int(os.getenv("MAX_CONCURRENT_SCRAPERS", "5")),
        "queue_size": int(os.getenv("QUEUE_SIZE", "100"))
    }


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get global settings instance.
    
    Returns:
        Settings instance
    """
    return settings


def reload_settings() -> Settings:
    """
    Reload settings from environment variables.
    
    Returns:
        New Settings instance
    """
    global settings
    settings = Settings()
    return settings


def get_database_url() -> str:
    """
    Get database connection URL.
    
    Returns:
        Database URL string
    """
    db = settings.DATABASE
    return f"postgresql+asyncpg://{db['db_user']}:{db['db_password']}@{db['db_host']}:{db['db_port']}/{db['db_name']}"


def get_redis_url() -> str:
    """
    Get Redis connection URL.
    
    Returns:
        Redis URL string
    """
    redis = settings.REDIS
    password_part = f":{redis['redis_password']}@" if redis['redis_password'] else "@"
    return f"redis://{password_part}{redis['redis_host']}:{redis['redis_port']}/{redis['redis_db']}"
