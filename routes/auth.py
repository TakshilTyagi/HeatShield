from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db_connection
from locations import get_all_states, get_cities_by_state, get_wards_by_city, get_city_by_id

auth_bp = Blueprint("auth", __name__)

def validate_and_format_phone(phone_input: str):
    """
    Validate 10-digit Indian mobile number (+91 format).
    Returns (is_valid, formatted_phone).
    """
    if not phone_input:
        return True, ""
    cleaned = phone_input.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]
    
    if len(cleaned) == 10 and cleaned.isdigit() and cleaned[0] in "6789":
        return True, f"+91{cleaned}"
    return False, ""

@auth_bp.route("/")
def home():
    """Application Entry Point: Always opens the Login page directly."""
    return redirect(url_for("auth.login"))

@auth_bp.route("/about")
def about():
    """Public Explanatory Page: Explain problem in 3 sentences, 3-step solution."""
    return render_template("home.html")

@auth_bp.route("/toggle-lang")
def toggle_lang():
    """Toggle language between English and Hindi."""
    curr = session.get("lang", "en")
    session["lang"] = "hi" if curr == "en" else "en"
    return redirect(request.referrer or url_for("auth.login"))

@auth_bp.route("/toggle-text-size")
def toggle_text_size():
    """Toggle large text mode for elder-friendly readability."""
    curr = session.get("large_text", False)
    session["large_text"] = not curr
    return redirect(request.referrer or url_for("auth.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login for all roles with friendly error validation."""
    if request.method == "GET":
        # Keep accessibility/language settings, but reset authenticated user session
        preserved_lang = session.get("lang", "en")
        preserved_large_text = session.get("large_text", False)
        session.clear()
        session["lang"] = preserved_lang
        session["large_text"] = preserved_large_text
        session.permanent = False

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template("login.html")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        city_name = "Your City"
        if user and user["city_id"]:
            cursor.execute("SELECT name FROM locations WHERE id = ?", (user["city_id"],))
            c_row = cursor.fetchone()
            if c_row:
                city_name = c_row["name"]

        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            # Populate non-permanent session (discarded automatically when app/browser closes)
            session.permanent = False
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["name"] = user["name"]
            session["city_id"] = user["city_id"]
            session["city_name"] = city_name

            flash(f"Welcome back, {user['name']}!", "success")

            # Route by role
            if user["role"] == "super_admin":
                return redirect(url_for("admin.super_overview"))
            elif user["role"] == "admin":
                return redirect(url_for("admin.dashboard"))
            elif user["role"] == "volunteer":
                return redirect(url_for("volunteer.visits"))
            elif user["role"] == "resident":
                return redirect(url_for("resident.dashboard"))
            return redirect(url_for("auth.login"))
        else:
            flash("Invalid username or password. Please try again.", "danger")

    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Allow resident or volunteer self-registration with State > City > Ward selection.
    All data is scoped to the user's city.
    """
    conn = get_db_connection()
    states = get_all_states(conn)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        name = request.form.get("name", "").strip()
        raw_phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "resident").strip()
        city_id_raw = request.form.get("city_id")
        ward_id_raw = request.form.get("ward_id")
        custom_ward = request.form.get("custom_ward", "").strip()
        address = request.form.get("address", "").strip()
        lat_raw = request.form.get("latitude")
        lon_raw = request.form.get("longitude")

        # Validation
        if not username or not password or not name:
            conn.close()
            flash("Username, password, and full name are required.", "danger")
            return render_template("register.html", states=states)

        if role not in ["resident", "volunteer"]:
            conn.close()
            flash("Invalid role selection.", "danger")
            return render_template("register.html", states=states)

        is_valid_phone, formatted_phone = validate_and_format_phone(raw_phone)
        if not is_valid_phone:
            conn.close()
            flash("Please enter a valid 10-digit Indian mobile number (+91).", "danger")
            return render_template("register.html", states=states)

        if not city_id_raw or not city_id_raw.isdigit():
            conn.close()
            flash("Please select your State and City.", "danger")
            return render_template("register.html", states=states)

        city_id = int(city_id_raw)
        city_record = get_city_by_id(conn, city_id)
        if not city_record:
            conn.close()
            flash("Invalid city selected.", "danger")
            return render_template("register.html", states=states)

        # Ward determination
        ward_id = None
        ward_name = "Not listed (Pending)"
        if ward_id_raw and ward_id_raw.isdigit():
            ward_id = int(ward_id_raw)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM locations WHERE id = ? AND parent_id = ?", (ward_id, city_id))
            w_row = cursor.fetchone()
            if w_row:
                ward_name = w_row["name"]
        elif custom_ward:
            ward_name = f"{custom_ward} (Pending)"

        # Coordinates
        try:
            latitude = float(lat_raw) if lat_raw else city_record["latitude"]
            longitude = float(lon_raw) if lon_raw else city_record["longitude"]
        except (ValueError, TypeError):
            latitude = city_record["latitude"] or 28.3667
            longitude = city_record["longitude"] or 79.4317

        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            flash("Username already exists. Please choose a unique username.", "danger")
            return render_template("register.html", states=states)

        # Create user
        pwd_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, name, phone, city_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, pwd_hash, role, name, formatted_phone, city_id))
        user_id = cursor.lastrowid

        # Profile based on role
        if role == "resident":
            cursor.execute("""
                INSERT INTO households (user_id, city_id, ward_id, ward, address, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, city_id, ward_id, ward_name, address or f"{ward_name}, {city_record['name']}", latitude, longitude))
        elif role == "volunteer":
            cursor.execute("""
                INSERT INTO volunteers (user_id, city_id, ward_id, ward, base_latitude, base_longitude)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, city_id, ward_id, ward_name, latitude, longitude))

        conn.commit()
        conn.close()

        flash("Registration successful! Please log in with your credentials.", "success")
        return redirect(url_for("auth.login"))

    conn.close()
    return render_template("register.html", states=states)

@auth_bp.route("/logout")
def logout():
    """Clear session data and redirect to login page."""
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for("auth.login"))
