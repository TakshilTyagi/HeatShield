import requests
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from risk import calculate_heat_index
from config import Config

# In-memory weather cache: key -> {"timestamp": float, "data": dict}
_WEATHER_CACHE: Dict[str, Dict[str, Any]] = {}

def get_cache_key(lat: float, lon: float) -> str:
    return f"{round(float(lat), 3)}_{round(float(lon), 3)}"

def fetch_weather(lat: float, lon: float, climate_zone: str = "plains", force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetch live weather from Open-Meteo API for specified coordinates with a 5.0 second timeout.
    Results are cached for Config.WEATHER_CACHE_MINUTES (default 30 mins).
    Falls back gracefully to deterministic simulated data if the API is offline or unreachable.
    """
    cache_key = get_cache_key(lat, lon)
    now_ts = time.time()
    cache_ttl_sec = Config.WEATHER_CACHE_MINUTES * 60

    if not force_refresh and cache_key in _WEATHER_CACHE:
        cached = _WEATHER_CACHE[cache_key]
        if (now_ts - cached["timestamp"]) < cache_ttl_sec:
            return cached["data"]

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code",
        "daily": "temperature_2m_max,apparent_temperature_max,precipitation_probability_max",
        "timezone": "Asia/Kolkata"
    }

    try:
        response = requests.get(url, params=params, timeout=Config.WEATHER_TIMEOUT_SECONDS)
        if response.status_code == 200:
            data = response.json()
            curr = data.get("current", {})
            temp_c = float(curr.get("temperature_2m", 36.0))
            humidity = float(curr.get("relative_humidity_2m", 50.0))
            
            # Recalculate Rothfusz heat index to ensure mathematical rigor
            heat_index_c = calculate_heat_index(temp_c, humidity)

            daily = data.get("daily", {})
            time_list = daily.get("time", [])
            temp_max_list = daily.get("temperature_2m_max", [])
            app_max_list = daily.get("apparent_temperature_max", [])

            forecast_days: List[Dict[str, Any]] = []
            for i in range(min(len(time_list), 4)):
                t_max = float(temp_max_list[i]) if i < len(temp_max_list) else temp_c
                app_max = float(app_max_list[i]) if i < len(app_max_list) else heat_index_c
                forecast_days.append({
                    "date": time_list[i],
                    "temp_max": t_max,
                    "heat_index": round(app_max, 1)
                })

            result = {
                "source": "Open-Meteo Live API",
                "temperature": round(temp_c, 1),
                "humidity": round(humidity, 1),
                "heat_index": heat_index_c,
                "weather_code": curr.get("weather_code", 0),
                "daily_forecast": forecast_days
            }

            _WEATHER_CACHE[cache_key] = {"timestamp": now_ts, "data": result}
            return result
    except Exception:
        # Graceful fallback on network timeout, DNS failure, or offline mode
        pass

    fallback_data = get_simulated_weather(lat, lon, climate_zone)
    _WEATHER_CACHE[cache_key] = {"timestamp": now_ts, "data": fallback_data}
    return fallback_data


def get_simulated_weather(lat: float, lon: float, climate_zone: str = "plains") -> Dict[str, Any]:
    """
    Deterministic simulated heatwave weather fallback per climate zone.
    Used when external API is unreachable or during offline development.
    """
    now = datetime.now()
    zone = (climate_zone or "plains").lower()

    if zone == "hill":
        temp_c = 28.5
        humidity = 55.0
    elif zone == "coastal":
        temp_c = 36.5
        humidity = 78.0
    else: # plains
        temp_c = 41.2
        humidity = 48.0

    heat_index_c = calculate_heat_index(temp_c, humidity)

    forecast_days = [
        {
            "date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
            "temp_max": round(temp_c + 0.8, 1),
            "heat_index": round(heat_index_c + 1.2, 1)
        },
        {
            "date": (now + timedelta(days=2)).strftime("%Y-%m-%d"),
            "temp_max": round(temp_c + 1.5, 1),
            "heat_index": round(heat_index_c + 2.0, 1)
        },
        {
            "date": (now + timedelta(days=3)).strftime("%Y-%m-%d"),
            "temp_max": round(temp_c - 0.5, 1),
            "heat_index": round(heat_index_c - 0.6, 1)
        }
    ]

    return {
        "source": "Simulated Weather (Offline Fallback)",
        "temperature": temp_c,
        "humidity": humidity,
        "heat_index": heat_index_c,
        "weather_code": 0,
        "daily_forecast": forecast_days
    }
