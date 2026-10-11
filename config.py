import os

class Config:
    """Application configuration for HeatShield."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "heatshield-secret-key-all-india-2026")
    
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    # Production / Container default: DATABASE_PATH env var, defaulting to /tmp/heatshield.db in production
    default_db = "/tmp/heatshield.db" if (os.environ.get("ENV") == "production" or os.name != "nt") else os.path.join(BASE_DIR, "heatshield.db")
    DB_PATH = os.environ.get("DATABASE_PATH", default_db)
    
    # Daily automated heat check secret token for Cron / Lambda / EventBridge
    HEAT_CHECK_TOKEN = os.environ.get("HEAT_CHECK_TOKEN", "hs-daily-token-all-india-secure")
    
    # Session lifecycle: browser session only (expires immediately when app or browser is closed)
    SESSION_PERMANENT = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Secure session cookies behind HTTPS (enabled in production or when HTTPS proxy is present)
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1") or os.environ.get("ENV") == "production"
    
    # Auto-reload templates when modified on disk
    TEMPLATES_AUTO_RELOAD = True
    
    # Weather caching & network constraints
    WEATHER_CACHE_MINUTES = int(os.environ.get("WEATHER_CACHE_MINUTES", 30))
    WEATHER_TIMEOUT_SECONDS = float(os.environ.get("WEATHER_TIMEOUT_SECONDS", 5.0))
    
    # Heat Index / Apparent Temperature thresholds per climate zone (°C)
    # Grounded in IMD heatwave criteria and physiological strain models
    HEAT_THRESHOLDS = {
        "plains": {
            "green_max": 35.0,
            "orange_max": 41.0,
            "description": "Standard Gangetic and peninsular plains criteria."
        },
        "coastal": {
            "green_max": 33.0,
            "orange_max": 38.0,
            "description": "High humidity zone; evaporative cooling impaired above 33°C."
        },
        "hill": {
            "green_max": 26.0,
            "orange_max": 30.0,
            "description": "Unacclimatized population & cold-insulated buildings; heat risk begins at 26°C."
        }
    }
    
    # AWS SNS Configuration
    AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_SNS_TOPIC_ARN = os.environ.get("AWS_SNS_TOPIC_ARN", "")
