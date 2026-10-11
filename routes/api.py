from flask import Blueprint, request, jsonify, current_app
from datetime import date
from database import get_db_connection, set_setting, get_setting
from routes.admin import auto_assign_visits_internal
from risk import get_heat_level
from weather import fetch_weather
from aws_services import send_alert
from config import Config
from locations import get_cities_by_state, get_wards_by_city, get_city_by_id

api_bp = Blueprint("api", __name__)

@api_bp.route("/locations/cities", methods=["GET"])
def api_get_cities():
    """Return JSON list of cities filtered by state name or state ID."""
    state_param = request.args.get("state") or request.args.get("state_id")
    if not state_param:
        return jsonify([]), 200

    conn = get_db_connection()
    cities = get_cities_by_state(conn, state_param)
    conn.close()

    result = [{"id": c["id"], "name": c["name"], "latitude": c["latitude"], "longitude": c["longitude"], "climate_zone": c["climate_zone"]} for c in cities]
    return jsonify(result), 200

@api_bp.route("/locations/wards", methods=["GET"])
def api_get_wards():
    """Return JSON list of wards configured for a city_id."""
    city_id_param = request.args.get("city_id")
    if not city_id_param or not city_id_param.isdigit():
        return jsonify([]), 200

    conn = get_db_connection()
    wards = get_wards_by_city(conn, int(city_id_param))
    conn.close()

    result = [{"id": w["id"], "name": w["name"], "latitude": w["latitude"], "longitude": w["longitude"]} for w in wards]
    return jsonify(result), 200

@api_bp.route("/daily-heat-check", methods=["POST"])
def daily_heat_check():
    """
    Automated Daily Heat Check Endpoint (PASS 2).
    Triggered every morning by AWS Lambda via EventBridge or cron.
    Protected by secret token header 'X-Heat-Token'.
    
    Loops over every active city, updates each city's level, auto-assigns visits,
    and sends a ward alert for Orange or Red cities.
    """
    token = request.headers.get("X-Heat-Token", "")
    expected_token = Config.HEAT_CHECK_TOKEN

    if not token or token != expected_token:
        return jsonify({"error": "Unauthorized: Invalid or missing X-Heat-Token"}), 401

    today_str = date.today().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.name, c.latitude, c.longitude, c.climate_zone, s.name as state_name
        FROM locations c
        LEFT JOIN locations s ON c.parent_id = s.id
        WHERE c.type = 'city'
    """)
    cities = cursor.fetchall()

    city_results = []
    total_assigned = 0

    for c in cities:
        c_id = c["id"]
        c_name = c["name"]
        c_lat = c["latitude"] or 28.3667
        c_lon = c["longitude"] or 79.4317
        c_zone = c["climate_zone"] or "plains"

        # Check if city has an active demo mode override
        c_demo = get_setting(conn, "demo_mode", city_id=c_id, default="auto")
        if c_demo in ["Green", "Orange", "Red"]:
            day_level = c_demo
            heat_index = 45.0 if day_level == "Red" else (38.0 if day_level == "Orange" else 30.0)
            weather_data = {"temperature": 40.0, "heat_index": heat_index}
        else:
            weather_data = fetch_weather(c_lat, c_lon, climate_zone=c_zone)
            heat_index = weather_data.get("heat_index", 32.0)
            day_level, _, _ = get_heat_level(heat_index, climate_zone=c_zone)

        # Update city settings
        set_setting(conn, "today_heat_level", day_level, city_id=c_id)

        # Auto-assign visits for this city
        assigned, total_hh = auto_assign_visits_internal(today_str, day_level, c_id)
        total_assigned += assigned

        # Dispatch alert if Orange or Red
        alert_status = "none"
        if day_level in ["Orange", "Red"]:
            msg = f"DAILY HEAT ADVISORY: {c_name} has moved to {day_level.upper()} level today (Heat Index {heat_index}°C). Check on vulnerable elders."
            res = send_alert("", msg)
            alert_status = res.get("status", "simulated")

            cursor.execute("""
                INSERT INTO alerts (city_id, title, message, target_ward, heat_level, dispatch_status)
                VALUES (?, ?, ?, 'All', ?, ?)
            """, (c_id, f"Morning {day_level} Alert", msg, day_level, alert_status))
            conn.commit()

        city_results.append({
            "city_id": c_id,
            "city_name": c_name,
            "heat_index": heat_index,
            "day_level": day_level,
            "assigned_visits": assigned,
            "total_households": total_hh,
            "alert_status": alert_status
        })

    cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (0, 'last_weather_check', CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "date": today_str,
        "cities_processed": len(city_results),
        "total_assigned_visits": total_assigned,
        "results": city_results
    }), 200
