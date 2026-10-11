from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import date, datetime
from database import get_db_connection, get_setting
from routes.decorators import role_required
from risk import get_heat_level
from weather import fetch_weather
from aws_services import send_alert
from locations import get_city_by_id, get_wards_by_city, get_all_states, get_cities_by_state
from routes.auth import validate_and_format_phone

resident_bp = Blueprint("resident", __name__)

def get_current_day_level(city_id: int):
    """Determine effective heat level considering city demo mode override, climate zone and coordinates."""
    conn = get_db_connection()
    demo_mode = get_setting(conn, "demo_mode", city_id=city_id, default="auto")
    city = get_city_by_id(conn, city_id)
    conn.close()

    lat = city["latitude"] if city and city["latitude"] else 28.3667
    lon = city["longitude"] if city and city["longitude"] else 79.4317
    climate_zone = city["climate_zone"] if city and city["climate_zone"] else "plains"

    if demo_mode in ["Green", "Orange", "Red"]:
        # Simulated temperature consistent with forced level
        sim_temp = 43.0 if demo_mode == "Red" else (37.5 if demo_mode == "Orange" else 29.0)
        sim_hi = 45.0 if demo_mode == "Red" else (38.5 if demo_mode == "Orange" else 30.0)
        return demo_mode, {
            "source": f"Admin Demo Override ({demo_mode})",
            "temperature": sim_temp,
            "humidity": 50.0,
            "heat_index": sim_hi,
            "weather_code": 0,
            "daily_forecast": []
        }, climate_zone

    w_data = fetch_weather(lat, lon, climate_zone=climate_zone)
    level_code, _, _ = get_heat_level(w_data.get("heat_index", 32.0), climate_zone=climate_zone)
    return level_code, w_data, climate_zone

@resident_bp.route("/dashboard")
@role_required("resident")
def dashboard():
    """Resident Dashboard: Heat status, 'I'm okay' check-in button, SOS, active alerts."""
    user_id = session["user_id"]
    today_str = date.today().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get household info with city details
    cursor.execute("""
        SELECT h.*, l.name as city_name, l.climate_zone, l.latitude as city_lat, l.longitude as city_lon
        FROM households h
        JOIN locations l ON h.city_id = l.id
        WHERE h.user_id = ?
    """, (user_id,))
    household = cursor.fetchone()
    if not household:
        conn.close()
        flash("Household profile missing. Please complete profile.", "warning")
        return redirect(url_for("resident.profile"))

    city_id = household["city_id"]

    # Get today's check-in
    cursor.execute("SELECT * FROM check_ins WHERE household_id = ? AND check_date = ?", (household["id"], today_str))
    today_checkin = cursor.fetchone()

    # Get active SOS
    cursor.execute("SELECT * FROM sos_alerts WHERE household_id = ? AND is_resolved = 0", (household["id"],))
    active_sos = cursor.fetchone()

    # Get latest alerts scoped to this city and ward
    cursor.execute("""
        SELECT * FROM alerts 
        WHERE city_id = ? AND target_ward IN (?, 'All') 
        ORDER BY created_at DESC LIMIT 3
    """, (city_id, household["ward"]))
    active_alerts = cursor.fetchall()
    conn.close()

    day_level, weather_info, climate_zone = get_current_day_level(city_id)

    return render_template(
        "resident_dashboard.html",
        household=household,
        day_level=day_level,
        weather=weather_info,
        today_checkin=today_checkin,
        active_sos=active_sos,
        alerts=active_alerts,
        today_date=today_str,
        climate_zone=climate_zone
    )

@resident_bp.route("/checkin", methods=["POST"])
@role_required("resident")
def checkin():
    """Single tap 'I'm okay' check-in with double-submission protection."""
    user_id = session["user_id"]
    today_str = date.today().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM households WHERE user_id = ?", (user_id,))
    household = cursor.fetchone()
    if not household:
        conn.close()
        flash("Household profile not found.", "danger")
        return redirect(url_for("resident.dashboard"))

    try:
        cursor.execute("""
            INSERT INTO check_ins (household_id, check_date, checked_at, status)
            VALUES (?, ?, CURRENT_TIMESTAMP, 'okay')
        """, (household["id"], today_str))
        conn.commit()
        flash("Thank you! Your check-in has been recorded. Your ward volunteer knows you are safe.", "success")
    except Exception:
        flash("You have already checked in for today.", "info")
    finally:
        conn.close()

    return redirect(url_for("resident.dashboard"))

@resident_bp.route("/sos", methods=["POST"])
@role_required("resident")
def trigger_sos():
    """Trigger emergency SOS beacon, notify emergency contact via SNS, and flag for ward office."""
    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT h.*, u.name, u.phone, l.name as city_name
        FROM households h 
        JOIN users u ON h.user_id = u.id 
        JOIN locations l ON h.city_id = l.id
        WHERE h.user_id = ?
    """, (user_id,))
    household = cursor.fetchone()

    if not household:
        conn.close()
        flash("Household profile not found.", "danger")
        return redirect(url_for("resident.dashboard"))

    # Check if there is already an open SOS
    cursor.execute("SELECT id FROM sos_alerts WHERE household_id = ? AND is_resolved = 0", (household["id"],))
    existing = cursor.fetchone()
    if not existing:
        cursor.execute("""
            INSERT INTO sos_alerts (household_id, created_at, is_resolved)
            VALUES (?, CURRENT_TIMESTAMP, 0)
        """, (household["id"],))
        conn.commit()

        # Send alert via Amazon SNS to emergency contact
        contact_phone = household["emergency_contact_phone"] or household["phone"]
        msg = f"EMERGENCY ALERT: {household['name']} at {household['address']} ({household['ward']}, {household['city_name']}) has triggered a HeatShield Heat SOS! Ward office and volunteers have been notified."
        send_alert(contact_phone, msg)

        flash("EMERGENCY BEACON ACTIVE! Your SOS alert has been transmitted to ward volunteers and your emergency contact. If critical, dial 112.", "danger")
    else:
        flash("Your active SOS is already registered with the ward emergency desk.", "warning")

    conn.close()
    return redirect(url_for("resident.dashboard"))

@resident_bp.route("/profile", methods=["GET", "POST"])
@role_required("resident")
def profile():
    """Resident Profile: Age, living alone, roof type, outdoor worker, medical needs, emergency contact."""
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM households WHERE user_id = ?", (user_id,))
    curr_h = cursor.fetchone()
    city_id = curr_h["city_id"] if curr_h else session.get("city_id")

    if request.method == "POST":
        age = request.form.get("age", 60)
        is_living_alone = 1 if request.form.get("is_living_alone") else 0
        roof_type = request.form.get("roof_type", "concrete")
        is_outdoor_worker = 1 if request.form.get("is_outdoor_worker") else 0
        job_type = request.form.get("job_type", "").strip()
        medical_needs = request.form.get("medical_needs", "").strip()
        ec_name = request.form.get("emergency_contact_name", "").strip()
        ec_phone_raw = request.form.get("emergency_contact_phone", "").strip()
        ward_id_raw = request.form.get("ward_id")
        custom_ward = request.form.get("custom_ward", "").strip()
        address = request.form.get("address", "").strip()
        lat = request.form.get("latitude")
        lon = request.form.get("longitude")

        is_valid_ec, ec_phone = validate_and_format_phone(ec_phone_raw)
        if not is_valid_ec:
            flash("Please enter a valid 10-digit Indian mobile number for emergency contact.", "danger")

        # Resolve ward
        ward_id = curr_h["ward_id"]
        ward_name = curr_h["ward"]
        if ward_id_raw and ward_id_raw.isdigit():
            ward_id = int(ward_id_raw)
            cursor.execute("SELECT name FROM locations WHERE id = ? AND parent_id = ?", (ward_id, city_id))
            w_row = cursor.fetchone()
            if w_row:
                ward_name = w_row["name"]
        elif custom_ward:
            ward_name = f"{custom_ward} (Pending)"

        try:
            latitude = float(lat) if lat else curr_h["latitude"]
            longitude = float(lon) if lon else curr_h["longitude"]
            age_int = int(age)
        except (ValueError, TypeError):
            latitude = curr_h["latitude"]
            longitude = curr_h["longitude"]
            age_int = 60

        cursor.execute("""
            UPDATE households
            SET age = ?, is_living_alone = ?, roof_type = ?, is_outdoor_worker = ?,
                job_type = ?, medical_needs = ?, emergency_contact_name = ?,
                emergency_contact_phone = ?, ward_id = ?, ward = ?, address = ?,
                latitude = ?, longitude = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (age_int, is_living_alone, roof_type, is_outdoor_worker, job_type,
              medical_needs, ec_name, ec_phone if is_valid_ec else ec_phone_raw,
              ward_id, ward_name, address, latitude, longitude, user_id))
        conn.commit()
        flash("Your vulnerability profile and location have been updated.", "success")

    cursor.execute("""
        SELECT h.*, u.name, u.phone, l.name as city_name
        FROM households h 
        JOIN users u ON h.user_id = u.id 
        JOIN locations l ON h.city_id = l.id
        WHERE h.user_id = ?
    """, (user_id,))
    household = cursor.fetchone()
    city_wards = get_wards_by_city(conn, household["city_id"])
    conn.close()

    return render_template("resident_profile.html", household=household, wards=city_wards)

@resident_bp.route("/cooling-points")
@role_required("resident")
def cooling_points():
    """Cooling shelters, water kiosks, and medical aid points map + list scoped to resident city."""
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT h.city_id, l.name as city_name, l.latitude as city_lat, l.longitude as city_lon
        FROM households h
        JOIN locations l ON h.city_id = l.id
        WHERE h.user_id = ?
    """, (user_id,))
    city_info = cursor.fetchone()

    city_id = city_info["city_id"] if city_info else session.get("city_id")

    cursor.execute("""
        SELECT * FROM cooling_points 
        WHERE city_id = ? AND is_open = 1 
        ORDER BY ward, name
    """, (city_id,))
    points = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return render_template("resident_cooling.html", cooling_points=points, city=city_info)

@resident_bp.route("/safety-guide")
def safety_guide():
    """Heat safety guide, first aid for heatstroke, safe hydration guidance."""
    return render_template("safety_guide.html")
