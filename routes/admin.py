from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response, jsonify
from datetime import date, datetime, timedelta
import csv
import io
from database import get_db_connection, get_setting, set_setting
from routes.decorators import role_required
from risk import calculate_household_risk, get_heat_level, calculate_3day_outlook
from weather import fetch_weather
from distance import haversine_distance
from aws_services import send_alert
from locations import get_city_by_id, get_wards_by_city, get_all_states, add_city, add_ward

admin_bp = Blueprint("admin", __name__)

def get_admin_city_id():
    """Get active city_id for the admin, allowing super_admin to switch city."""
    if session.get("role") == "super_admin":
        req_city = request.args.get("city_id") or request.form.get("city_id")
        if req_city and str(req_city).isdigit():
            return int(req_city)
        if session.get("city_id"):
            return int(session["city_id"])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM locations WHERE type = 'city' ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 1
    return int(session.get("city_id") or 1)

def auto_assign_visits_internal(today_str: str, day_level: str, city_id: int):
    """
    Core auto-assign algorithm:
    - Scoped strictly to city_id.
    - Sort city's households by risk score highest first.
    - Assign each to the volunteer in the same ward with fewest assignments so far (ties broken by distance).
    - If no volunteer in that ward, assign to any available volunteer in the city with capacity.
    - Cap around 8 households per volunteer per day.
    - Households that cannot be assigned remain unassigned.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get households in this city
    cursor.execute("""
        SELECT h.*, u.name, u.phone,
               (SELECT checked_at FROM check_ins WHERE household_id = h.id AND check_date = ?) AS checkin_time,
               (SELECT COUNT(*) FROM sos_alerts WHERE household_id = h.id AND is_resolved = 0) AS open_sos_count
        FROM households h
        JOIN users u ON h.user_id = u.id
        WHERE h.city_id = ?
    """, (today_str, city_id))
    households = cursor.fetchall()

    # Get active volunteers in this city
    cursor.execute("""
        SELECT v.*, u.name
        FROM volunteers v
        JOIN users u ON v.user_id = u.id
        WHERE v.city_id = ? AND v.is_active = 1
    """, (city_id,))
    volunteers = [dict(v) for v in cursor.fetchall()]

    if not volunteers:
        conn.close()
        return 0, len(households)

    # Count existing assignments for volunteers today
    vol_counts = {}
    cursor.execute("""
        SELECT a.volunteer_id, COUNT(*) as cnt 
        FROM assignments a
        JOIN volunteers v ON a.volunteer_id = v.id
        WHERE v.city_id = ? AND a.assigned_date = ? 
        GROUP BY a.volunteer_id
    """, (city_id, today_str))
    for row in cursor.fetchall():
        vol_counts[row["volunteer_id"]] = row["cnt"]
    for v in volunteers:
        vol_counts.setdefault(v["id"], 0)

    # Score households
    scored_households = []
    for h in households:
        h_dict = dict(h)
        has_checked_in = bool(h_dict.get("checkin_time"))
        has_sos = bool(h_dict.get("open_sos_count", 0) > 0)
        risk_res = calculate_household_risk(h_dict, day_level, has_checked_in, has_sos)
        scored_households.append({
            "household": h_dict,
            "score": risk_res["score"],
            "has_sos": has_sos
        })

    # Sort descending by risk score
    scored_households.sort(key=lambda x: (-1 if x["has_sos"] else 0, -x["score"]))

    assigned_count = 0
    MAX_CAP = 8

    for item in scored_households:
        h = item["household"]
        h_id = h["id"]
        h_ward = h["ward"]
        h_lat = h["latitude"]
        h_lon = h["longitude"]

        # Check if already assigned today
        cursor.execute("SELECT id FROM assignments WHERE household_id = ? AND assigned_date = ?", (h_id, today_str))
        if cursor.fetchone():
            continue

        # Candidate volunteers: first try same ward with capacity (< MAX_CAP)
        same_ward_candidates = [v for v in volunteers if v["ward"] == h_ward and vol_counts[v["id"]] < MAX_CAP]
        
        chosen_volunteer = None
        if same_ward_candidates:
            same_ward_candidates.sort(key=lambda v: (
                vol_counts[v["id"]],
                haversine_distance(v["base_latitude"], v["base_longitude"], h_lat, h_lon)
            ))
            chosen_volunteer = same_ward_candidates[0]
        else:
            # Try any volunteer in the city with capacity
            any_candidates = [v for v in volunteers if vol_counts[v["id"]] < MAX_CAP]
            if any_candidates:
                any_candidates.sort(key=lambda v: (
                    vol_counts[v["id"]],
                    haversine_distance(v["base_latitude"], v["base_longitude"], h_lat, h_lon)
                ))
                chosen_volunteer = any_candidates[0]

        if chosen_volunteer:
            cursor.execute("""
                INSERT INTO assignments (household_id, volunteer_id, assigned_date)
                VALUES (?, ?, ?)
            """, (h_id, chosen_volunteer["id"], today_str))
            vol_counts[chosen_volunteer["id"]] += 1
            assigned_count += 1

    conn.commit()
    conn.close()
    return assigned_count, len(households)


def get_admin_weather_and_level(city_id: int):
    """Retrieve weather and effective level for city_id."""
    conn = get_db_connection()
    city = get_city_by_id(conn, city_id)
    demo_mode = get_setting(conn, "demo_mode", city_id=city_id, default="auto")
    simulate_cutoff = bool(get_setting(conn, "simulate_cutoff", city_id=city_id, default="0") == "1")
    conn.close()

    lat = city["latitude"] if city and city["latitude"] else 28.3667
    lon = city["longitude"] if city and city["longitude"] else 79.4317
    climate_zone = city["climate_zone"] if city and city["climate_zone"] else "plains"

    live_weather = fetch_weather(lat, lon, climate_zone=climate_zone)

    if demo_mode in ["Green", "Orange", "Red"]:
        level_code = demo_mode
        if level_code == "Red":
            live_weather["temperature"] = 42.5
            live_weather["humidity"] = 52.0
            live_weather["heat_index"] = 45.1
        elif level_code == "Orange":
            live_weather["temperature"] = 37.0
            live_weather["humidity"] = 45.0
            live_weather["heat_index"] = 38.5
        else:
            live_weather["temperature"] = 30.0
            live_weather["humidity"] = 40.0
            live_weather["heat_index"] = 31.0
    else:
        level_code, _, _ = get_heat_level(live_weather.get("heat_index", 32.0), climate_zone=climate_zone)

    return level_code, live_weather, demo_mode, simulate_cutoff, city


@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    """Ward Admin Operations Dashboard scoped to user's city."""
    city_id = get_admin_city_id()
    today_str = date.today().isoformat()
    day_level, weather_data, demo_mode, simulate_cutoff, city_info = get_admin_weather_and_level(city_id)

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Total households in this city
    cursor.execute("SELECT COUNT(*) FROM households WHERE city_id = ?", (city_id,))
    total_households = cursor.fetchone()[0]

    # 2. Checked today in this city
    cursor.execute("""
        SELECT COUNT(*) FROM check_ins c
        JOIN households h ON c.household_id = h.id
        WHERE h.city_id = ? AND c.check_date = ?
    """, (city_id, today_str))
    checked_today = cursor.fetchone()[0]

    # 3. Active volunteers in this city
    cursor.execute("SELECT COUNT(*) FROM volunteers WHERE city_id = ? AND is_active = 1", (city_id,))
    active_volunteers = cursor.fetchone()[0]

    # 4. Open SOS count in this city
    cursor.execute("""
        SELECT COUNT(*) FROM sos_alerts s
        JOIN households h ON s.household_id = h.id
        WHERE h.city_id = ? AND s.is_resolved = 0
    """, (city_id,))
    open_sos_count = cursor.fetchone()[0]

    # 5. Active SOS list in this city
    cursor.execute("""
        SELECT s.*, h.address, h.ward, h.latitude, h.longitude, u.name, u.phone
        FROM sos_alerts s
        JOIN households h ON s.household_id = h.id
        JOIN users u ON h.user_id = u.id
        WHERE h.city_id = ? AND s.is_resolved = 0
        ORDER BY s.created_at ASC
    """, (city_id,))
    open_sos_alerts = [dict(row) for row in cursor.fetchall()]

    # 6. Check-ins by day for Chart.js (past 7 days in this city)
    chart_dates = []
    chart_counts = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM check_ins c
            JOIN households h ON c.household_id = h.id
            WHERE h.city_id = ? AND c.check_date = ?
        """, (city_id, d))
        cnt = cursor.fetchone()[0]
        chart_dates.append(d[5:]) # MM-DD
        chart_counts.append(cnt)

    # 7. Households for Leaflet Map with calculated risk
    cursor.execute("""
        SELECT h.*, u.name, u.phone,
               (SELECT checked_at FROM check_ins WHERE household_id = h.id AND check_date = ?) AS checkin_time,
               (SELECT COUNT(*) FROM sos_alerts WHERE household_id = h.id AND is_resolved = 0) AS has_sos
        FROM households h
        JOIN users u ON h.user_id = u.id
        WHERE h.city_id = ?
    """, (today_str, city_id))
    all_hh = cursor.fetchall()

    map_points = []
    unchecked_high_risk = 0

    for h in all_hh:
        h_dict = dict(h)
        has_checked_in = bool(h_dict.get("checkin_time"))
        has_sos = bool(h_dict.get("has_sos", 0) > 0)
        risk_res = calculate_household_risk(h_dict, day_level, has_checked_in, has_sos)

        if not has_checked_in and risk_res["score"] >= 60:
            unchecked_high_risk += 1

        map_points.append({
            "id": h_dict["id"],
            "name": h_dict["name"],
            "ward": h_dict["ward"],
            "lat": h_dict["latitude"],
            "lon": h_dict["longitude"],
            "score": risk_res["score"],
            "category": risk_res["category"],
            "reasons": risk_res["reasons"],
            "has_checked_in": has_checked_in,
            "has_sos": has_sos
        })

    # 8. Cooling centres for map in this city
    cursor.execute("SELECT * FROM cooling_points WHERE city_id = ?", (city_id,))
    cooling_points_list = [dict(cp) for cp in cursor.fetchall()]

    conn.close()

    # AI/ML 3-day heat outlook
    climate_zone = city_info["climate_zone"] if city_info else "plains"
    outlook = calculate_3day_outlook(weather_data.get("daily_forecast", []), climate_zone=climate_zone)

    return render_template(
        "admin_dashboard.html",
        total_households=total_households,
        checked_today=checked_today,
        unchecked_high_risk=unchecked_high_risk,
        open_sos_count=open_sos_count,
        active_volunteers=active_volunteers,
        open_sos_alerts=open_sos_alerts,
        map_points=map_points,
        cooling_points=cooling_points_list,
        chart_dates=chart_dates,
        chart_counts=chart_counts,
        day_level=day_level,
        weather=weather_data,
        demo_mode=demo_mode,
        simulate_cutoff=simulate_cutoff,
        outlook=outlook,
        city=city_info,
        city_id=city_id
    )


@admin_bp.route("/households")
@role_required("admin")
def households():
    """Households management table scoped to city: search, filter by ward and risk, reassign."""
    city_id = get_admin_city_id()
    today_str = date.today().isoformat()
    day_level, _, _, _, city_info = get_admin_weather_and_level(city_id)

    search_query = request.args.get("search", "").strip()
    filter_ward = request.args.get("ward", "").strip()
    filter_risk = request.args.get("risk", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Volunteers in this city for assignment dropdown
    cursor.execute("""
        SELECT v.id, u.name, v.ward 
        FROM volunteers v 
        JOIN users u ON v.user_id = u.id 
        WHERE v.city_id = ? AND v.is_active = 1
    """, (city_id,))
    volunteers = [dict(v) for v in cursor.fetchall()]

    # Query households in this city
    cursor.execute("""
        SELECT h.*, u.name, u.phone,
               (SELECT checked_at FROM check_ins WHERE household_id = h.id AND check_date = ?) AS checkin_time,
               (SELECT COUNT(*) FROM sos_alerts WHERE household_id = h.id AND is_resolved = 0) AS has_sos,
               (SELECT a.volunteer_id FROM assignments a WHERE a.household_id = h.id AND a.assigned_date = ?) AS assigned_vol_id,
               (SELECT u2.name FROM assignments a JOIN volunteers v2 ON a.volunteer_id = v2.id JOIN users u2 ON v2.user_id = u2.id WHERE a.household_id = h.id AND a.assigned_date = ?) AS assigned_vol_name
        FROM households h
        JOIN users u ON h.user_id = u.id
        WHERE h.city_id = ?
    """, (today_str, today_str, today_str, city_id))
    rows = cursor.fetchall()
    city_wards = get_wards_by_city(conn, city_id)
    conn.close()

    households_list = []
    for r in rows:
        h_dict = dict(r)
        has_checked_in = bool(h_dict.get("checkin_time"))
        has_sos = bool(h_dict.get("has_sos", 0) > 0)
        risk_res = calculate_household_risk(h_dict, day_level, has_checked_in, has_sos)

        # Apply filters
        if search_query and (search_query.lower() not in h_dict["name"].lower() and search_query.lower() not in h_dict["address"].lower()):
            continue
        if filter_ward and h_dict["ward"] != filter_ward:
            continue
        if filter_risk and risk_res["category"] != filter_risk:
            continue

        households_list.append({
            **h_dict,
            "score": risk_res["score"],
            "category": risk_res["category"],
            "reasons": risk_res["reasons"],
            "has_checked_in": has_checked_in
        })

    # Sort by score descending
    households_list.sort(key=lambda x: -x["score"])

    return render_template(
        "admin_households.html",
        households=households_list,
        volunteers=volunteers,
        wards=[w["name"] for w in city_wards],
        search_query=search_query,
        filter_ward=filter_ward,
        filter_risk=filter_risk,
        city=city_info,
        city_id=city_id
    )


@admin_bp.route("/reassign", methods=["POST"])
@role_required("admin")
def reassign_volunteer():
    """Manually assign or reassign a household to a volunteer for today."""
    city_id = get_admin_city_id()
    today_str = date.today().isoformat()
    household_id = request.form.get("household_id")
    volunteer_id = request.form.get("volunteer_id")

    if not household_id or not volunteer_id:
        flash("Invalid assignment request.", "danger")
        return redirect(url_for("admin.households", city_id=city_id))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify household belongs to admin's city
    cursor.execute("SELECT id FROM households WHERE id = ? AND city_id = ?", (household_id, city_id))
    if not cursor.fetchone():
        conn.close()
        flash("Unauthorized: household does not belong to your city.", "danger")
        return redirect(url_for("admin.households", city_id=city_id))

    if volunteer_id == "unassign":
        cursor.execute("DELETE FROM assignments WHERE household_id = ? AND assigned_date = ?", (household_id, today_str))
        flash("Household unassigned.", "info")
    else:
        # Verify volunteer belongs to same city
        cursor.execute("SELECT id FROM volunteers WHERE id = ? AND city_id = ?", (volunteer_id, city_id))
        if not cursor.fetchone():
            conn.close()
            flash("Unauthorized: volunteer does not belong to your city.", "danger")
            return redirect(url_for("admin.households", city_id=city_id))

        cursor.execute("""
            INSERT INTO assignments (household_id, volunteer_id, assigned_date)
            VALUES (?, ?, ?)
            ON CONFLICT(household_id, assigned_date) DO UPDATE SET volunteer_id = excluded.volunteer_id
        """, (household_id, volunteer_id, today_str))
        flash("Volunteer assignment updated.", "success")

    conn.commit()
    conn.close()
    return redirect(url_for("admin.households", city_id=city_id))


@admin_bp.route("/auto-assign", methods=["POST"])
@role_required("admin")
def auto_assign():
    """Trigger auto-assignment algorithm for current city."""
    city_id = get_admin_city_id()
    today_str = date.today().isoformat()
    day_level, _, _, _, _ = get_admin_weather_and_level(city_id)
    assigned, total = auto_assign_visits_internal(today_str, day_level, city_id)
    flash(f"Auto-assign completed for your city: {assigned} household visits allocated across field volunteers.", "success")
    return redirect(url_for("admin.dashboard", city_id=city_id))


@admin_bp.route("/set-demo-mode", methods=["POST"])
@role_required("admin")
def set_demo_mode():
    """Change Demo mode override (auto, Green, Orange, Red) and auto-assign on Orange/Red."""
    city_id = get_admin_city_id()
    mode = request.form.get("demo_mode", "auto")

    conn = get_db_connection()
    set_setting(conn, "demo_mode", mode, city_id=city_id)
    city_record = get_city_by_id(conn, city_id)
    conn.close()

    city_name = city_record["name"] if city_record else "Your City"
    today_str = date.today().isoformat()

    if mode in ["Orange", "Red"]:
        # Auto-assign runs automatically when Demo mode changes to Orange/Red
        auto_assign_visits_internal(today_str, mode, city_id)
        # Dispatch alert
        send_alert("", f"EMERGENCY ADVISORY: {city_name} has moved to {mode.upper()} Heat Alert. Volunteer visits initiated.")
        flash(f"Demo mode set to {mode.upper()} for {city_name}. Alerts dispatched and visit routes auto-assigned.", "warning")
    else:
        flash(f"Demo weather mode set to {mode} for {city_name}.", "info")

    return redirect(url_for("admin.dashboard", city_id=city_id))


@admin_bp.route("/toggle-cutoff", methods=["POST"])
@role_required("admin")
def toggle_cutoff():
    """Toggle simulation of 12:00 PM cutoff rule for this city."""
    city_id = get_admin_city_id()
    conn = get_db_connection()
    current_val = get_setting(conn, "simulate_cutoff", city_id=city_id, default="0")
    new_val = "0" if current_val == "1" else "1"
    set_setting(conn, "simulate_cutoff", new_val, city_id=city_id)
    conn.close()

    if new_val == "1":
        flash("Simulated 12:00 PM cutoff activated! Unchecked high-risk households in your city are now flagged at top of volunteer lists.", "warning")
    else:
        flash("Simulated 12:00 PM cutoff deactivated.", "info")

    return redirect(url_for("admin.dashboard", city_id=city_id))


@admin_bp.route("/sos-cases")
@role_required("admin")
def sos_cases():
    """SOS cases log with resolution tracker and response time scoped to city."""
    city_id = get_admin_city_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, h.address, h.ward, u.name, u.phone
        FROM sos_alerts s
        JOIN households h ON s.household_id = h.id
        JOIN users u ON h.user_id = u.id
        WHERE h.city_id = ?
        ORDER BY s.is_resolved ASC, s.created_at DESC
    """, (city_id,))
    cases = []
    for row in cursor.fetchall():
        item = dict(row)
        if item["is_resolved"] and item["resolved_at"]:
            try:
                t1 = datetime.fromisoformat(str(item["created_at"]))
                t2 = datetime.fromisoformat(str(item["resolved_at"]))
                diff_min = max(1, int((t2 - t1).total_seconds() / 60))
                item["response_time_min"] = diff_min
            except Exception:
                item["response_time_min"] = "N/A"
        else:
            item["response_time_min"] = "Active"
        cases.append(item)
    city_info = get_city_by_id(conn, city_id)
    conn.close()

    return render_template("admin_sos.html", cases=cases, city=city_info, city_id=city_id)


@admin_bp.route("/resolve-sos", methods=["POST"])
@role_required("admin")
def resolve_sos():
    """Mark an active SOS case as resolved with response notes."""
    city_id = get_admin_city_id()
    sos_id = request.form.get("sos_id")
    notes = request.form.get("notes", "Resolved by municipal emergency desk.").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sos_alerts 
        SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP, resolution_notes = ?
        WHERE id = ? AND household_id IN (SELECT id FROM households WHERE city_id = ?)
    """, (notes, sos_id, city_id))
    conn.commit()
    conn.close()

    flash("SOS alert resolved and response logged.", "success")
    return redirect(url_for("admin.sos_cases", city_id=city_id))


@admin_bp.route("/cooling-centres", methods=["GET", "POST"])
@role_required("admin")
def cooling_centres():
    """Cooling centres management (PASS 2): add, edit, open/close, capacity, occupancy."""
    city_id = get_admin_city_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    city_info = get_city_by_id(conn, city_id)
    city_wards = get_wards_by_city(conn, city_id)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name")
            p_type = request.form.get("point_type", "shelter")
            ward = request.form.get("ward", city_wards[0]["name"] if city_wards else "Central")
            addr = request.form.get("address", "")
            lat = float(request.form.get("latitude") or (city_info["latitude"] if city_info else 28.3667))
            lon = float(request.form.get("longitude") or (city_info["longitude"] if city_info else 79.4317))
            cap = int(request.form.get("capacity", 50))
            cursor.execute("""
                INSERT INTO cooling_points (city_id, name, point_type, ward, address, latitude, longitude, capacity, occupancy, is_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
            """, (city_id, name, p_type, ward, addr, lat, lon, cap))
            conn.commit()
            flash("New cooling facility registered for your city.", "success")
        elif action == "toggle_open":
            c_id = request.form.get("id")
            cursor.execute("UPDATE cooling_points SET is_open = CASE WHEN is_open = 1 THEN 0 ELSE 1 END WHERE id = ? AND city_id = ?", (c_id, city_id))
            conn.commit()
            flash("Facility operational status updated.", "info")
        elif action == "update_occupancy":
            c_id = request.form.get("id")
            occ = int(request.form.get("occupancy", 0))
            cursor.execute("UPDATE cooling_points SET occupancy = ? WHERE id = ? AND city_id = ?", (occ, c_id, city_id))
            conn.commit()
            flash("Occupancy count updated.", "success")

    cursor.execute("SELECT * FROM cooling_points WHERE city_id = ? ORDER BY ward, name", (city_id,))
    centres = [dict(c) for c in cursor.fetchall()]
    conn.close()

    return render_template("admin_cooling.html", centres=centres, wards=[w["name"] for w in city_wards], city=city_info, city_id=city_id)


@admin_bp.route("/alerts", methods=["GET", "POST"])
@role_required("admin")
def alerts():
    """Send and view broadcast heat alerts with Amazon SNS integration scoped to city."""
    city_id = get_admin_city_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    city_info = get_city_by_id(conn, city_id)
    city_wards = get_wards_by_city(conn, city_id)

    if request.method == "POST":
        title = request.form.get("title", "Heat Advisory").strip()
        message = request.form.get("message", "").strip()
        target_ward = request.form.get("target_ward", "All")
        heat_level = request.form.get("heat_level", "Orange")

        if not message:
            flash("Please enter an alert message.", "danger")
        else:
            city_name = city_info["name"] if city_info else "City"
            sns_res = send_alert("", f"[{city_name.upper()} {title.upper()}] {message}")
            status = sns_res["status"]

            cursor.execute("""
                INSERT INTO alerts (city_id, title, message, target_ward, heat_level, dispatch_status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (city_id, title, message, target_ward, heat_level, status))
            conn.commit()
            flash(f"Broadcast alert sent ({status.title()}).", "success")

    cursor.execute("SELECT * FROM alerts WHERE city_id = ? ORDER BY created_at DESC", (city_id,))
    all_alerts = cursor.fetchall()
    conn.close()

    return render_template("admin_alerts.html", alerts=all_alerts, wards=[w["name"] for w in city_wards], city=city_info, city_id=city_id)


@admin_bp.route("/reports")
@role_required("admin")
def reports():
    """Weekly summary report of households reached, SOS incidents, and response time (PASS 2)."""
    city_id = get_admin_city_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    city_info = get_city_by_id(conn, city_id)

    # Total visits in last 7 days in this city
    cursor.execute("""
        SELECT COUNT(*) FROM visits v
        JOIN households h ON v.household_id = h.id
        WHERE h.city_id = ?
    """, (city_id,))
    total_visits = cursor.fetchone()[0]

    # Total SOS in last 7 days in this city
    cursor.execute("""
        SELECT COUNT(*) FROM sos_alerts s
        JOIN households h ON s.household_id = h.id
        WHERE h.city_id = ?
    """, (city_id,))
    total_sos = cursor.fetchone()[0]

    # Resolved SOS and avg response time
    cursor.execute("""
        SELECT s.created_at, s.resolved_at FROM sos_alerts s
        JOIN households h ON s.household_id = h.id
        WHERE h.city_id = ? AND s.is_resolved = 1
    """, (city_id,))
    resolved_rows = cursor.fetchall()
    times = []
    for r in resolved_rows:
        try:
            t1 = datetime.fromisoformat(str(r["created_at"]))
            t2 = datetime.fromisoformat(str(r["resolved_at"]))
            times.append(max(1, (t2 - t1).total_seconds() / 60))
        except Exception:
            pass
    avg_response = round(sum(times) / len(times), 1) if times else 0.0

    # Supplies distributed
    cursor.execute("""
        SELECT v.supplies_given, COUNT(*) as cnt 
        FROM visits v
        JOIN households h ON v.household_id = h.id
        WHERE h.city_id = ? AND v.supplies_given != 'none' 
        GROUP BY v.supplies_given
    """, (city_id,))
    supplies_summary = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_reports.html",
        total_visits=total_visits,
        total_sos=total_sos,
        avg_response=avg_response,
        supplies_summary=supplies_summary,
        city=city_info,
        city_id=city_id
    )


@admin_bp.route("/reports/download-csv")
@role_required("admin")
def download_csv():
    """Generate and stream CSV report of visit logs for current city."""
    city_id = get_admin_city_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.id, v.visit_date, v.status, v.supplies_given, v.notes, v.visited_at,
               u_vol.name AS volunteer_name, u_res.name AS resident_name, h.ward, h.address
        FROM visits v
        JOIN volunteers vol ON v.volunteer_id = vol.id
        JOIN users u_vol ON vol.user_id = u_vol.id
        JOIN households h ON v.household_id = h.id
        JOIN users u_res ON h.user_id = u_res.id
        WHERE h.city_id = ?
        ORDER BY v.visited_at DESC
    """, (city_id,))
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Visit ID", "Date", "Time", "Volunteer", "Resident", "Ward", "Address", "Status", "Supplies Given", "Notes"])

    for r in rows:
        writer.writerow([
            r["id"], r["visit_date"], r["visited_at"], r["volunteer_name"],
            r["resident_name"], r["ward"], r["address"], r["status"],
            r["supplies_given"], r["notes"]
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=heatshield_visit_report_city{city_id}_{date.today().isoformat()}.csv"}
    )


# =========================================================================
# SUPER ADMIN OVERVIEW (PASS 2)
# =========================================================================

@admin_bp.route("/super")
@role_required("super_admin")
def super_overview():
    """
    Super Admin Overview:
    - Sortable table of all cities: (today's level, households, unchecked high-risk, open SOS, volunteers).
    - Leaflet map of India with one marker per city coloured by heat level.
    - Global Demo mode override switch.
    - Form to add new cities and wards.
    """
    today_str = date.today().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    global_demo_mode = get_setting(conn, "demo_mode", city_id=0, default="auto")

    # Get all cities
    cursor.execute("""
        SELECT c.id, c.name, c.latitude, c.longitude, c.climate_zone, s.name as state_name
        FROM locations c
        LEFT JOIN locations s ON c.parent_id = s.id
        WHERE c.type = 'city'
        ORDER BY s.name ASC, c.name ASC
    """)
    cities = cursor.fetchall()
    states = get_all_states(conn)

    cities_summary = []
    map_markers = []

    for c in cities:
        c_id = c["id"]
        c_name = c["name"]
        c_lat = c["latitude"] or 28.3667
        c_lon = c["longitude"] or 79.4317
        c_zone = c["climate_zone"]

        # Today's level for this city
        c_demo = get_setting(conn, "demo_mode", city_id=c_id, default="auto")
        effective_demo = c_demo if c_demo != "auto" else global_demo_mode

        if effective_demo in ["Green", "Orange", "Red"]:
            level = effective_demo
            hi = 45.0 if level == "Red" else (38.0 if level == "Orange" else 30.0)
        else:
            w = fetch_weather(c_lat, c_lon, climate_zone=c_zone)
            hi = w.get("heat_index", 32.0)
            level, _, _ = get_heat_level(hi, climate_zone=c_zone)

        # Total households
        cursor.execute("SELECT COUNT(*) FROM households WHERE city_id = ?", (c_id,))
        h_count = cursor.fetchone()[0]

        # Active volunteers
        cursor.execute("SELECT COUNT(*) FROM volunteers WHERE city_id = ? AND is_active = 1", (c_id,))
        v_count = cursor.fetchone()[0]

        # Open SOS
        cursor.execute("""
            SELECT COUNT(*) FROM sos_alerts s
            JOIN households h ON s.household_id = h.id
            WHERE h.city_id = ? AND s.is_resolved = 0
        """, (c_id,))
        sos_count = cursor.fetchone()[0]

        # Unchecked high-risk
        cursor.execute("""
            SELECT h.*,
                   (SELECT checked_at FROM check_ins WHERE household_id = h.id AND check_date = ?) AS checkin_time,
                   (SELECT COUNT(*) FROM sos_alerts WHERE household_id = h.id AND is_resolved = 0) AS has_sos
            FROM households h
            WHERE h.city_id = ?
        """, (today_str, c_id))
        c_hh = cursor.fetchall()
        unchecked_hr = 0
        for hh in c_hh:
            if not hh["checkin_time"]:
                r = calculate_household_risk(dict(hh), level, False, bool(hh["has_sos"]))
                if r["score"] >= 60:
                    unchecked_hr += 1

        cities_summary.append({
            "id": c_id,
            "name": c_name,
            "state": c["state_name"],
            "zone": c_zone,
            "level": level,
            "heat_index": hi,
            "households": h_count,
            "volunteers": v_count,
            "open_sos": sos_count,
            "unchecked_high_risk": unchecked_hr,
            "latitude": c_lat,
            "longitude": c_lon
        })

        map_markers.append({
            "id": c_id,
            "name": c_name,
            "state": c["state_name"],
            "lat": c_lat,
            "lon": c_lon,
            "level": level,
            "heat_index": hi,
            "households": h_count,
            "volunteers": v_count,
            "open_sos": sos_count
        })

    conn.close()

    return render_template(
        "admin_super.html",
        cities=cities_summary,
        map_markers=map_markers,
        states=states,
        global_demo_mode=global_demo_mode
    )


@admin_bp.route("/super/set-global-demo", methods=["POST"])
@role_required("super_admin")
def set_global_demo():
    """Set global demo weather override across all Indian cities."""
    mode = request.form.get("demo_mode", "auto")
    conn = get_db_connection()
    set_setting(conn, "demo_mode", mode, city_id=0)
    conn.close()

    flash(f"Global demo mode set to {mode.upper()} across all cities.", "warning" if mode in ["Orange", "Red"] else "info")
    return redirect(url_for("admin.super_overview"))


@admin_bp.route("/super/add-city", methods=["POST"])
@role_required("super_admin")
def super_add_city():
    """Add a new city location to the nationwide network."""
    state_name = request.form.get("state_name", "").strip()
    city_name = request.form.get("city_name", "").strip()
    zone = request.form.get("climate_zone", "plains").strip()
    lat_raw = request.form.get("latitude")
    lon_raw = request.form.get("longitude")

    if not state_name or not city_name:
        flash("State and City names are required.", "danger")
        return redirect(url_for("admin.super_overview"))

    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except (ValueError, TypeError):
        flash("Valid latitude and longitude numbers are required.", "danger")
        return redirect(url_for("admin.super_overview"))

    conn = get_db_connection()
    c_id = add_city(conn, state_name, city_name, lat, lon, zone)
    # Seed default ward for new city
    add_ward(conn, c_id, "Central Ward", lat, lon)
    conn.close()

    flash(f"City {city_name} ({state_name}) registered successfully in {zone} zone.", "success")
    return redirect(url_for("admin.super_overview"))


@admin_bp.route("/super/add-ward", methods=["POST"])
@role_required("super_admin")
def super_add_ward():
    """Add a new municipal ward to any city."""
    city_id_raw = request.form.get("city_id")
    ward_name = request.form.get("ward_name", "").strip()
    lat_raw = request.form.get("latitude")
    lon_raw = request.form.get("longitude")

    if not city_id_raw or not ward_name:
        flash("City and Ward name are required.", "danger")
        return redirect(url_for("admin.super_overview"))

    conn = get_db_connection()
    city_id = int(city_id_raw)
    city = get_city_by_id(conn, city_id)
    lat = float(lat_raw) if lat_raw else city["latitude"]
    lon = float(lon_raw) if lon_raw else city["longitude"]

    add_ward(conn, city_id, ward_name, lat, lon)
    conn.close()

    flash(f"Ward {ward_name} created under {city['name']}.", "success")
    return redirect(url_for("admin.super_overview"))
