import math
from typing import Dict, Any, List, Tuple
from config import Config

def calculate_heat_index(temp_c: float, rel_humidity: float) -> float:
    """
    Calculate the Heat Index (Apparent Temperature) in Celsius using
    the official NOAA / NWS Rothfusz regression equation.
    
    Valid primarily when Temp >= 26.7 C (80 F) and RH >= 40%.
    Outside this range or in cool weather, returns temp_c.
    """
    if temp_c is None or rel_humidity is None:
        return 30.0

    # Convert Celsius to Fahrenheit
    t_f = (temp_c * 9.0 / 5.0) + 32.0
    rh = float(rel_humidity)

    # Screening formula (Steadman simplification)
    hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))
    avg_test = (hi_simple + t_f) / 2.0

    if avg_test < 80.0:
        heat_index_f = hi_simple
    else:
        # Full 9-term Rothfusz regression
        heat_index_f = (
            -42.379
            + (2.04901523 * t_f)
            + (10.14333127 * rh)
            - (0.22475541 * t_f * rh)
            - (0.00683783 * (t_f ** 2))
            - (0.05481717 * (rh ** 2))
            + (0.00122874 * (t_f ** 2) * rh)
            + (0.00085282 * t_f * (rh ** 2))
            - (0.00000199 * (t_f ** 2) * (rh ** 2))
        )

        # Low humidity adjustment
        if rh < 13.0 and 80.0 <= t_f <= 112.0:
            diff = 17.0 - abs(t_f - 95.0)
            if diff > 0:
                adj = ((13.0 - rh) / 4.0) * math.sqrt(diff / 17.0)
                heat_index_f -= adj

        # High humidity adjustment
        elif rh > 85.0 and 80.0 <= t_f <= 87.0:
            adj = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
            heat_index_f += adj

    # Convert result back to Celsius
    heat_index_c = (heat_index_f - 32.0) * (5.0 / 9.0)
    return round(heat_index_c, 1)


def get_heat_level(heat_index_c: float, climate_zone: str = "plains") -> Tuple[str, str, str]:
    """
    Categorize day heat level based on Heat Index (C) and the city's Climate Zone.
    
    Climate Zones:
    - plains:  Green < 35 C, Orange 35 - 41 C, Red > 41 C
    - coastal: Green < 33 C, Orange 33 - 38 C, Red > 38 C
    - hill:    Green < 26 C, Orange 26 - 30 C, Red > 30 C
    
    Returns (level_code, level_title, explanation).
    """
    zone = (climate_zone or "plains").lower()
    thresholds = Config.HEAT_THRESHOLDS.get(zone, Config.HEAT_THRESHOLDS["plains"])
    green_max = thresholds["green_max"]
    orange_max = thresholds["orange_max"]

    if heat_index_c < green_max:
        return (
            "Green",
            "Normal / Safe",
            f"Conditions normal for {zone} region (Heat index < {green_max}°C). Standard hydration advised."
        )
    elif heat_index_c <= orange_max:
        return (
            "Orange",
            "High Alert / Moderate Heatwave",
            f"Elevated heat index for {zone} region ({green_max}-{orange_max}°C). High vulnerability households prioritized."
        )
    else:
        return (
            "Red",
            "Severe Heatwave / Emergency",
            f"Dangerous heat index for {zone} region (>{orange_max}°C). Active volunteer outreach and cooling operations."
        )


def calculate_household_risk(household: Dict[str, Any], day_level: str, has_checked_in_today: bool, has_open_sos: bool) -> Dict[str, Any]:
    """
    Calculate an explainable household risk score (0 to 100) based on strict vulnerability rules:
    - age 60+: +25 (75+: +30)
    - lives alone: +20
    - tin or asbestos roof: +15
    - outdoor worker: +10
    - medical need entered: +15
    - no check-in today (Orange/Red days): +20
    - open unresolved SOS: +25
    Cap at 100.
    
    Returns a dict with 'score', 'category', 'reasons', and 'missed_cutoff'.
    """
    score = 0
    reasons: List[str] = []

    # 1. Age factor
    age = household.get("age") or 0
    if age >= 75:
        score += 30
        reasons.append(f"Age {age} (75+ vulnerable senior)")
    elif age >= 60:
        score += 25
        reasons.append(f"Age {age} (Senior citizen 60+)")

    # 2. Living alone
    if household.get("is_living_alone"):
        score += 20
        reasons.append("Lives alone (No family nearby)")

    # 3. Roof type
    roof_type = (household.get("roof_type") or "").lower()
    if roof_type in ["tin", "asbestos"]:
        score += 15
        reasons.append(f"{roof_type.title()} roof (Severe indoor heat trap)")
    elif roof_type == "thatched":
        score += 10
        reasons.append("Thatched roof (Low thermal insulation)")

    # 4. Outdoor worker
    if household.get("is_outdoor_worker"):
        job = household.get("job_type") or "outdoor labour"
        score += 10
        reasons.append(f"Outdoor worker ({job})")

    # 5. Medical needs
    medical = (household.get("medical_needs") or "").strip()
    if medical:
        score += 15
        reasons.append(f"Medical vulnerability ({medical[:30]}...)")

    # 6. Check-in status on Orange / Red days
    is_hot_day = day_level in ["Orange", "Red"]
    if is_hot_day and not has_checked_in_today:
        score += 20
        reasons.append("No check-in received today")

    # 7. Open unresolved SOS
    if has_open_sos:
        score += 25
        reasons.append("ACTIVE SOS ALERT: Immediate help requested")

    # Final score capped at 100
    final_score = min(score, 100)

    # Risk level label
    if final_score >= 70 or has_open_sos:
        category = "Critical"
    elif final_score >= 45:
        category = "Moderate"
    else:
        category = "Low"

    # Missed check-in rule: On Orange/Red days, score 60+ and not checked in
    missed_cutoff = bool(is_hot_day and not has_checked_in_today and final_score >= 60)

    return {
        "score": final_score,
        "category": category,
        "reasons": reasons,
        "missed_cutoff": missed_cutoff
    }


def calculate_3day_outlook(daily_forecasts: List[Dict[str, Any]], climate_zone: str = "plains") -> Dict[str, Any]:
    """
    Explainable 3-day heat outlook derived from forecast temperatures and heat index.
    Informs ward admins of impending heatwave trends and red-alert days.
    """
    if not daily_forecasts:
        return {
            "trend": "Stable",
            "trend_explanation": "Forecast data unavailable; maintaining current alert readiness.",
            "red_days_count": 0,
            "days": []
        }

    # Analyze first 3 forecast days
    first_three = daily_forecasts[:3]
    red_count = 0
    temps = []

    days_summary = []
    for day in first_three:
        hi = day.get("heat_index", 30.0)
        level, _, _ = get_heat_level(hi, climate_zone)
        if level == "Red":
            red_count += 1
        temps.append(day.get("temp_max", 35.0))
        days_summary.append({
            "date": day.get("date", "Upcoming"),
            "temp_max": day.get("temp_max"),
            "heat_index": hi,
            "level": level
        })

    # Determine trend
    if len(temps) >= 2:
        diff = temps[-1] - temps[0]
        if diff >= 1.5:
            trend = "Hotter"
            trend_text = f"Temperatures projected to rise by {round(diff, 1)}°C over the next 3 days."
        elif diff <= -1.5:
            trend = "Cooler"
            trend_text = f"Temperatures projected to decline by {round(abs(diff), 1)}°C."
        else:
            trend = "Stable"
            trend_text = "Temperatures will remain relatively steady over the next 72 hours."
    else:
        trend = "Stable"
        trend_text = "Stable weather expected."

    return {
        "trend": trend,
        "trend_explanation": trend_text,
        "red_days_count": red_count,
        "days": days_summary
    }
