from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import date
import json
from database import get_db_connection, get_setting
from routes.decorators import role_required
from risk import calculate_household_risk, get_heat_level
from distance import haversine_distance
from weather import fetch_weather
from locations import get_city_by_id

volunteer_bp = Blueprint("volunteer", __name__)

def get_current_day_level(city_id: int):
    """Determine effective heat level considering city demo mode override."""
    conn = get_db_connection()
    demo_mode = get_setting(conn, "demo_mode", city_id=city_id, default="auto")
    city = get_city_by_id(conn, city_id)
    conn.close()

    lat = city["latitude"] if city and city["latitude"] else 28.3667
    lon = city["longitude"] if city and city["longitude"] else 79.4317
    climate_zone = city["climate_zone"] if city and city["climate_zone"] else "plains"

    if demo_mode in ["Green", "Orange", "Red"]:
        return demo_mode

    w_data = fetch_weather(lat, lon, climate_zone=climate_zone)
    level_code, _, _ = get_heat_level(w_data.get("heat_index", 32.0), climate_zone=climate_zone)
    return level_code

def is_simulated_cutoff_active(city_id: int):
    """Check if admin triggered the 12:00 PM cutoff simulation for this city."""
    conn = get_db_connection()
    val = get_setting(conn, "simulate_cutoff", city_id=city_id, default="0")
    conn.close()
    return bool(val == "1")

@volunteer_bp.route("/visits")
@role_required("volunteer")
def visits():
    """
    Today's visits: shows ONLY households assigned to this volunteer.
    Sorted by risk score highest first, ties broken by distance nearest first.
    Missed-check-in households always at the top!
    """
    user_id = session["user_id"]
    today_str = date.today().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get volunteer record with city info
    cursor.execute("""
        SELECT v.*, l.name as city_name 
        FROM volunteers v
        LEFT JOIN locations l ON v.city_id = l.id
        WHERE v.user_id = ?
    """, (user_id,))
    vol = cursor.fetchone()
    if not vol:
        conn.close()
        flash("Volunteer profile not found.", "danger")
        return redirect(url_for("auth.home"))

    city_id = vol["city_id"]
    vol_lat = vol["base_latitude"]
    vol_lon = vol["base_longitude"]

    day_level = get_current_day_level(city_id)
    sim_cutoff = is_simulated_cutoff_active(city_id)

    # Fetch assigned households for today
    cursor.execute("""
        SELECT a.id AS assignment_id, h.*, u.name, u.phone,
               (SELECT checked_at FROM check_ins WHERE household_id = h.id AND check_date = ?) AS checkin_time,
               (SELECT COUNT(*) FROM sos_alerts WHERE household_id = h.id AND is_resolved = 0) AS open_sos_count,
               (SELECT status FROM visits WHERE household_id = h.id AND visit_date = ? ORDER BY id DESC LIMIT 1) AS last_visit_status,
               (SELECT supplies_given FROM visits WHERE household_id = h.id AND visit_date = ? ORDER BY id DESC LIMIT 1) AS last_supplies
        FROM assignments a
        JOIN households h ON a.household_id = h.id
        JOIN users u ON h.user_id = u.id
        WHERE a.volunteer_id = ? AND a.assigned_date = ?
    """, (today_str, today_str, today_str, vol["id"], today_str))
    assigned_rows = cursor.fetchall()
    conn.close()

    visits_list = []
    for r in assigned_rows:
        h_dict = dict(r)
        has_checked_in = bool(h_dict.get("checkin_time"))
        has_sos = bool(h_dict.get("open_sos_count", 0) > 0)

        # Calculate risk score
        risk_res = calculate_household_risk(h_dict, day_level, has_checked_in, has_sos)
        
        # Calculate distance from volunteer base
        dist = haversine_distance(vol_lat, vol_lon, h_dict["latitude"], h_dict["longitude"])

        # Missed check-in rule: Orange/Red day + score 60+ + not checked in + (simulated cutoff or past noon)
        is_missed = bool(risk_res["missed_cutoff"] and sim_cutoff)

        visits_list.append({
            "assignment_id": h_dict["assignment_id"],
            "household_id": h_dict["id"],
            "name": h_dict["name"],
            "phone": h_dict["phone"],
            "ward": h_dict["ward"],
            "address": h_dict["address"],
            "score": risk_res["score"],
            "category": risk_res["category"],
            "reasons": risk_res["reasons"],
            "distance_km": dist,
            "has_checked_in": has_checked_in,
            "has_sos": has_sos,
            "is_missed": is_missed,
            "last_visit_status": h_dict.get("last_visit_status"),
            "last_supplies": h_dict.get("last_supplies")
        })

    # SORTING:
    # 1. Missed-check-in households always at the top (-1 if is_missed else 0)
    # 2. Risk score descending (-score)
    # 3. Distance ascending (dist)
    visits_list.sort(key=lambda x: (
        -1 if (x["is_missed"] or x["has_sos"]) else 0,
        -x["score"],
        x["distance_km"]
    ))

    return render_template(
        "volunteer_visits.html",
        visits=visits_list,
        volunteer=vol,
        day_level=day_level,
        sim_cutoff=sim_cutoff
    )

@volunteer_bp.route("/record-visit", methods=["POST"])
@role_required("volunteer")
def record_visit():
    """Log visit status: Checked (safe), Needs help, or Not reachable + supplies given."""
    user_id = session["user_id"]
    today_str = date.today().isoformat()

    household_id = request.form.get("household_id")
    assignment_id = request.form.get("assignment_id")
    status = request.form.get("status", "checked")
    supplies_given = request.form.get("supplies_given", "none")
    notes = request.form.get("notes", "").strip()

    if not household_id or status not in ["checked", "needs_help", "not_reachable"]:
        flash("Invalid visit submission data.", "danger")
        return redirect(url_for("volunteer.visits"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM volunteers WHERE user_id = ?", (user_id,))
    vol = cursor.fetchone()
    if not vol:
        conn.close()
        flash("Volunteer profile missing.", "danger")
        return redirect(url_for("auth.home"))

    cursor.execute("""
        INSERT INTO visits (assignment_id, volunteer_id, household_id, visit_date, status, supplies_given, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (assignment_id, vol["id"], household_id, today_str, status, supplies_given, notes))

    # If status is "needs_help", also ensure an SOS or alert is flagged
    if status == "needs_help":
        cursor.execute("SELECT id FROM sos_alerts WHERE household_id = ? AND is_resolved = 0", (household_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO sos_alerts (household_id, created_at, is_resolved, resolution_notes)
                VALUES (?, CURRENT_TIMESTAMP, 0, 'Flagged by volunteer visit as needing immediate assistance.')
            """, (household_id,))

    conn.commit()
    conn.close()

    flash(f"Visit recorded successfully ({status.replace('_', ' ').title()}).", "success")
    return redirect(url_for("volunteer.visits"))

@volunteer_bp.route("/activity")
@role_required("volunteer")
def activity():
    """Volunteer activity log, completed visits count, and badges."""
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM volunteers WHERE user_id = ?", (user_id,))
    vol = cursor.fetchone()

    cursor.execute("""
        SELECT v.*, h.address, h.ward, u.name AS resident_name
        FROM visits v
        JOIN households h ON v.household_id = h.id
        JOIN users u ON h.user_id = u.id
        WHERE v.volunteer_id = ?
        ORDER BY v.visited_at DESC LIMIT 20
    """, (vol["id"],))
    recent_visits = cursor.fetchall()

    # Total count
    cursor.execute("SELECT COUNT(*) FROM visits WHERE volunteer_id = ?", (vol["id"],))
    total_count = cursor.fetchone()[0]

    # Badges calculation
    earned_badges = ["Active Volunteer"]
    if total_count >= 1:
        earned_badges.append("First Responder")
    if total_count >= 5:
        earned_badges.append("Hydration Hero")
    if total_count >= 10:
        earned_badges.append("Heat Guardian")

    conn.close()

    return render_template(
        "volunteer_activity.html",
        volunteer=vol,
        recent_visits=recent_visits,
        total_count=total_count,
        badges=earned_badges
    )

@volunteer_bp.route("/update-location", methods=["POST"])
@role_required("volunteer")
def update_location():
    """Update volunteer base GPS coordinates."""
    user_id = session["user_id"]
    lat = request.form.get("latitude")
    lon = request.form.get("longitude")

    try:
        latitude = float(lat)
        longitude = float(lon)
    except (ValueError, TypeError):
        flash("Invalid coordinates provided.", "danger")
        return redirect(url_for("volunteer.visits"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE volunteers 
        SET base_latitude = ?, base_longitude = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (latitude, longitude, user_id))
    conn.commit()
    conn.close()

    flash("Your volunteer base location has been updated.", "success")
    return redirect(url_for("volunteer.visits"))
