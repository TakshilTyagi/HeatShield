import sqlite3
import os
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash
from config import Config
from locations import sync_locations_to_db, add_ward

def get_db_connection():
    """Create and return a thread-safe connection with sqlite3.Row row factory."""
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Create all required tables with foreign keys, constraints and indexes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Locations table (State > City > Ward hierarchy)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL CHECK(type IN ('state', 'city', 'ward')),
        name TEXT NOT NULL,
        parent_id INTEGER,
        latitude REAL,
        longitude REAL,
        climate_zone TEXT NOT NULL DEFAULT 'plains' CHECK(climate_zone IN ('plains', 'coastal', 'hill')),
        FOREIGN KEY (parent_id) REFERENCES locations (id) ON DELETE CASCADE
    );
    """)

    # 2. Users table (authentication and role-based access scoped by city)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('super_admin', 'admin', 'volunteer', 'resident')),
        name TEXT NOT NULL,
        phone TEXT,
        city_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (city_id) REFERENCES locations (id) ON DELETE SET NULL
    );
    """)

    # 3. Households table (resident vulnerability profiles)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS households (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        city_id INTEGER NOT NULL,
        ward_id INTEGER,
        ward TEXT NOT NULL,
        address TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        age INTEGER NOT NULL DEFAULT 60,
        is_living_alone INTEGER NOT NULL DEFAULT 0,
        roof_type TEXT NOT NULL DEFAULT 'concrete' CHECK(roof_type IN ('concrete', 'tin', 'asbestos', 'thatched')),
        is_outdoor_worker INTEGER NOT NULL DEFAULT 0,
        job_type TEXT DEFAULT '',
        medical_needs TEXT DEFAULT '',
        emergency_contact_name TEXT DEFAULT '',
        emergency_contact_phone TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (city_id) REFERENCES locations (id) ON DELETE CASCADE,
        FOREIGN KEY (ward_id) REFERENCES locations (id) ON DELETE SET NULL
    );
    """)

    # 4. Volunteers table (base location and coverage)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS volunteers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        city_id INTEGER NOT NULL,
        ward_id INTEGER,
        ward TEXT NOT NULL,
        base_latitude REAL NOT NULL,
        base_longitude REAL NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        badges TEXT DEFAULT '[]',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (city_id) REFERENCES locations (id) ON DELETE CASCADE,
        FOREIGN KEY (ward_id) REFERENCES locations (id) ON DELETE SET NULL
    );
    """)

    # 5. Check-ins table (daily resident confirmations)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS check_ins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        household_id INTEGER NOT NULL,
        check_date DATE NOT NULL,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'okay',
        UNIQUE(household_id, check_date),
        FOREIGN KEY (household_id) REFERENCES households (id) ON DELETE CASCADE
    );
    """)

    # 6. Assignments table (daily volunteer to household routing)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        household_id INTEGER NOT NULL,
        volunteer_id INTEGER NOT NULL,
        assigned_date DATE NOT NULL,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(household_id, assigned_date),
        FOREIGN KEY (household_id) REFERENCES households (id) ON DELETE CASCADE,
        FOREIGN KEY (volunteer_id) REFERENCES volunteers (id) ON DELETE CASCADE
    );
    """)

    # 7. Visits table (volunteer visit field reports)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER,
        volunteer_id INTEGER NOT NULL,
        household_id INTEGER NOT NULL,
        visit_date DATE NOT NULL,
        visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL CHECK(status IN ('checked', 'needs_help', 'not_reachable')),
        supplies_given TEXT DEFAULT 'none',
        notes TEXT DEFAULT '',
        FOREIGN KEY (volunteer_id) REFERENCES volunteers (id) ON DELETE CASCADE,
        FOREIGN KEY (household_id) REFERENCES households (id) ON DELETE CASCADE
    );
    """)

    # 8. SOS Alerts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sos_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        household_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_resolved INTEGER NOT NULL DEFAULT 0,
        resolved_at TIMESTAMP,
        resolution_notes TEXT DEFAULT '',
        FOREIGN KEY (household_id) REFERENCES households (id) ON DELETE CASCADE
    );
    """)

    # 9. Cooling Points table (shelters, kiosks, clinics)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cooling_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id INTEGER NOT NULL,
        ward_id INTEGER,
        name TEXT NOT NULL,
        point_type TEXT NOT NULL CHECK(point_type IN ('shelter', 'water_kiosk', 'hospital')),
        ward TEXT NOT NULL,
        address TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        capacity INTEGER NOT NULL DEFAULT 50,
        occupancy INTEGER NOT NULL DEFAULT 0,
        is_open INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (city_id) REFERENCES locations (id) ON DELETE CASCADE,
        FOREIGN KEY (ward_id) REFERENCES locations (id) ON DELETE SET NULL
    );
    """)

    # 10. Alerts table (broadcast messages from ward office)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        target_ward TEXT NOT NULL DEFAULT 'All',
        heat_level TEXT NOT NULL DEFAULT 'Orange',
        dispatch_status TEXT NOT NULL DEFAULT 'simulated',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (city_id) REFERENCES locations (id) ON DELETE CASCADE
    );
    """)

    # 11. Settings table (demo overrides, simulation state per city or global)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        city_id INTEGER NOT NULL DEFAULT 0,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        PRIMARY KEY (city_id, key)
    );
    """)

    conn.commit()

    # Populate locations from india_cities.json
    sync_locations_to_db(conn)
    conn.close()

def get_setting(conn, key: str, city_id: int = 0, default: str = "auto") -> str:
    """Retrieve setting for a specific city, falling back to global (city_id=0)."""
    cursor = conn.cursor()
    # Check city-specific setting
    if city_id > 0:
        cursor.execute("SELECT value FROM settings WHERE city_id = ? AND key = ?", (city_id, key))
        row = cursor.fetchone()
        if row and row["value"]:
            return row["value"]

    # Check global setting
    cursor.execute("SELECT value FROM settings WHERE city_id = 0 AND key = ?", (key,))
    row = cursor.fetchone()
    if row and row["value"]:
        return row["value"]

    return default

def set_setting(conn, key: str, value: str, city_id: int = 0):
    """Save setting for city_id (0 = global)."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO settings (city_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(city_id, key) DO UPDATE SET value = excluded.value
    """, (city_id, key, value))
    conn.commit()

def seed_db(pass_level: int = 1):
    """
    Populate database with demo data across verified Indian cities.
    PASS 1 seeds: 1 Super Admin + 2 Demo Cities (Bareilly & Jaipur).
    PASS 2 adds: 3 Demo Cities (Chennai, Kolkata, Shimla).
    """
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if Super Admin already exists
    cursor.execute("SELECT id FROM users WHERE username = 'superadmin'")
    if cursor.fetchone():
        conn.close()
        return

    # 1. Super Admin (Oversight across all Indian cities)
    cursor.execute("""
        INSERT INTO users (username, password_hash, role, name, phone, city_id)
        VALUES ('superadmin', ?, 'super_admin', 'National Disaster Control Officer', '+919876543000', NULL)
    """, (generate_password_hash("admin123"),))

    # Helper to find city and ward IDs
    def find_city(name):
        cursor.execute("SELECT id, name, climate_zone, latitude, longitude FROM locations WHERE type = 'city' AND name = ?", (name,))
        return cursor.fetchone()

    def get_or_create_ward(city_id, ward_name, lat, lon):
        cursor.execute("SELECT id FROM locations WHERE type = 'ward' AND parent_id = ? AND name = ?", (city_id, ward_name))
        row = cursor.fetchone()
        if row:
            return row[0]
        return add_ward(conn, city_id, ward_name, lat, lon)

    # ========================================================
    # DEMO CITY 1: BAREILLY (Uttar Pradesh - Plains)
    # ========================================================
    bareilly = find_city("Bareilly")
    if bareilly:
        b_id = bareilly["id"]
        # Wards in Bareilly
        w_quila = get_or_create_ward(b_id, "Quila", 28.3620, 79.4120)
        w_civil = get_or_create_ward(b_id, "Civil Lines", 28.3670, 79.4304)
        w_subhash = get_or_create_ward(b_id, "Subhash Nagar", 28.3490, 79.4080)
        w_cbganj = get_or_create_ward(b_id, "C.B. Ganj", 28.3950, 79.3620)
        w_oldcity = get_or_create_ward(b_id, "Old City", 28.3540, 79.4240)
        w_izzat = get_or_create_ward(b_id, "Izzatnagar", 28.3980, 79.4350)

        # Ward Admin Bareilly
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, name, phone, city_id)
            VALUES ('admin', ?, 'admin', 'Bareilly Ward Control Officer', '+919876543200', ?)
        """, (generate_password_hash("admin123"), b_id))

        # Volunteers Bareilly
        b_vols = [
            ("vol_amit", "vol123", "Amit Verma", "+919876543201", "Quila", w_quila, 28.3625, 79.4125),
            ("vol_priya", "vol123", "Priya Sharma", "+919876543202", "Civil Lines", w_civil, 28.3665, 79.4295),
            ("vol_rahul", "vol123", "Rahul Saxena", "+919876543203", "Subhash Nagar", w_subhash, 28.3495, 79.4085)
        ]
        for uname, pwd, name, phone, w_name, w_idx, vlat, vlon in b_vols:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'volunteer', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, b_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO volunteers (user_id, city_id, ward_id, ward, base_latitude, base_longitude, badges)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (u_id, b_id, w_idx, w_name, vlat, vlon, '["First Responder", "Hydration Hero"]'))

        # Residents Bareilly
        b_residents = [
            ("res_ram", "res123", "Ram Prasad", "+919876543210", "Quila", w_quila, "House 14, Gali 3, Quila", 28.3622, 79.4122, 78, 1, "tin", 0, "", "Chronic hypertension", "Deepak (Son)", "+919876500001"),
            ("res_shanti", "res123", "Shanti Devi", "+919876543211", "Quila", w_quila, "Near Jama Masjid, Quila", 28.3630, 79.4130, 68, 1, "tin", 0, "", "Joint arthritis", "Anita (Niece)", "+919876500002"),
            ("res_mohan", "res123", "Mohan Lal", "+919876543212", "Quila", w_quila, "Plot 42, Purana Pul Road, Quila", 28.3615, 79.4110, 52, 0, "asbestos", 1, "Cycle-rickshaw puller", "Asthma", "Sunita (Wife)", "+919876500003"),
            ("res_kamla", "res123", "Kamla Bai", "+919876543213", "Civil Lines", w_civil, "Behind Town Hall, Civil Lines", 28.3675, 79.4310, 76, 1, "tin", 0, "", "Diabetes type 2", "Rajesh (Neighbor)", "+919876500004"),
            ("res_jagdish", "res123", "Jagdish Chandra", "+919876543214", "Civil Lines", w_civil, "12 Railway Colony Road", 28.3685, 79.4290, 81, 1, "concrete", 0, "", "Heart ailment", "Dr. Alok", "+919876500005"),
            ("res_dinesh", "res123", "Dinesh Kumar", "+919876543215", "Civil Lines", w_civil, "Station Road Vendor Kiosk", 28.3660, 79.4325, 46, 0, "tin", 1, "Street fruit vendor", "", "Geeta (Sister)", "+919876500006"),
            ("res_saroj", "res123", "Sarojini Devi", "+919876543216", "Subhash Nagar", w_subhash, "Quarter 8B, Subhash Nagar", 28.3490, 79.4075, 74, 1, "asbestos", 0, "", "High blood pressure", "Pooja (Daughter)", "+919876500007"),
            ("res_mukesh", "res123", "Mukesh Yadav", "+919876543217", "Subhash Nagar", w_subhash, "Near Canal Bridge, Subhash Nagar", 28.3480, 79.4090, 62, 0, "concrete", 0, "", "", "Amit (Son)", "+919876500008"),
            ("res_kailash", "res123", "Kailash Nath", "+919876543218", "Subhash Nagar", w_subhash, "Bada Chauraha, Subhash Nagar", 28.3510, 79.4060, 83, 1, "tin", 0, "", "Mobility impaired", "Suresh (Brother)", "+919876500009"),
            ("res_babu", "res123", "Babu Ram", "+919876543219", "C.B. Ganj", w_cbganj, "Labour Colony, Ganj Road", 28.3955, 79.3625, 49, 0, "tin", 1, "Construction bricklayer", "Chronic dehydration history", "Malti (Wife)", "+919876500010"),
            ("res_champa", "res123", "Champa Devi", "+919876543220", "C.B. Ganj", w_cbganj, "Near Sugar Mill, C.B. Ganj", 28.3940, 79.3610, 79, 1, "thatched", 0, "", "Kidney weakness", "Vipin (Son)", "+919876500011"),
            ("res_anwar", "res123", "Anwar Hussain", "+919876543221", "Old City", w_oldcity, "Near Zari Market, Old City", 28.3545, 79.4235, 77, 1, "tin", 0, "", "Cardiac bypass history", "Tariq (Nephew)", "+919876500012"),
            ("res_fatima", "res123", "Fatima Bi", "+919876543222", "Old City", w_oldcity, "Katra Manrai, Old City", 28.3535, 79.4250, 69, 0, "concrete", 0, "", "Hypertension", "Salma (Daughter)", "+919876500013"),
            ("res_harish", "res123", "Harish Rawat", "+919876543223", "Izzatnagar", w_izzat, "Near DRM Office Colony", 28.3975, 79.4345, 71, 1, "asbestos", 0, "", "Asthma", "Neeraj (Son)", "+919876500014"),
            ("res_vimla", "res123", "Vimla Joshi", "+919876543224", "Izzatnagar", w_izzat, "Workshops Gate 2, Izzatnagar", 28.3985, 79.4360, 65, 0, "concrete", 0, "", "", "Pradeep (Husband)", "+919876500015")
        ]
        for uname, pwd, name, phone, w_name, w_idx, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone in b_residents:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'resident', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, b_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO households (user_id, city_id, ward_id, ward, address, latitude, longitude, age, is_living_alone, roof_type, is_outdoor_worker, job_type, medical_needs, emergency_contact_name, emergency_contact_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (u_id, b_id, w_idx, w_name, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone))

        # Cooling Points Bareilly
        b_cool = [
            ("Nagar Nigam Community Shelter", "shelter", "Civil Lines", w_civil, "Near Town Hall, Civil Lines", 28.3670, 79.4300, 100, 24, 1),
            ("District Hospital Cold Care Wing", "hospital", "Civil Lines", w_civil, "Station Road, Civil Lines", 28.3680, 79.4320, 40, 15, 1),
            ("Quila Public Jal Sewa Kiosk", "water_kiosk", "Quila", w_quila, "Chowk Bazar, Quila", 28.3620, 79.4128, 200, 80, 1),
            ("Subhash Nagar Rain Basera", "shelter", "Subhash Nagar", w_subhash, "Near Railway Crossing", 28.3492, 79.4082, 60, 18, 1)
        ]
        for name, ptype, w_name, w_idx, addr, lat, lon, cap, occ, is_o in b_cool:
            cursor.execute("""
                INSERT INTO cooling_points (city_id, ward_id, name, point_type, ward, address, latitude, longitude, capacity, occupancy, is_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (b_id, w_idx, name, ptype, w_name, addr, lat, lon, cap, occ, is_o))

        # Alert Bareilly
        cursor.execute("""
            INSERT INTO alerts (city_id, title, message, target_ward, heat_level, dispatch_status)
            VALUES (?, 'Heat Advisory Issued', 'High temperature forecast for your city today. Public water kiosks are operational.', 'All', 'Orange', 'simulated')
        """, (b_id,))

        # Settings
        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'demo_mode', 'auto')", (b_id,))
        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'simulate_cutoff', '0')", (b_id,))

    # ========================================================
    # DEMO CITY 2: JAIPUR (Rajasthan - Plains)
    # ========================================================
    jaipur = find_city("Jaipur")
    if jaipur:
        j_id = jaipur["id"]
        # Wards Jaipur
        w_cscheme = get_or_create_ward(j_id, "C-Scheme", 26.9100, 75.7980)
        w_johari = get_or_create_ward(j_id, "Johari Bazar", 26.9200, 75.8240)
        w_mansarovar = get_or_create_ward(j_id, "Mansarovar", 26.8550, 75.7650)
        w_malviya = get_or_create_ward(j_id, "Malviya Nagar", 26.8520, 75.8150)

        # Ward Admin Jaipur
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, name, phone, city_id)
            VALUES ('admin_jaipur', ?, 'admin', 'Jaipur Nagar Nigam Control Officer', '+919876543300', ?)
        """, (generate_password_hash("admin123"), j_id))

        # Volunteers Jaipur
        j_vols = [
            ("vol_vikram", "vol123", "Vikram Rathore", "+919876543301", "Johari Bazar", w_johari, 26.9205, 75.8245),
            ("vol_sunita", "vol123", "Sunita Shekhawat", "+919876543302", "C-Scheme", w_cscheme, 26.9095, 75.7975)
        ]
        for uname, pwd, name, phone, w_name, w_idx, vlat, vlon in j_vols:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'volunteer', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, j_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO volunteers (user_id, city_id, ward_id, ward, base_latitude, base_longitude, badges)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (u_id, j_id, w_idx, w_name, vlat, vlon, '["First Responder"]'))

        # Residents Jaipur
        j_residents = [
            ("res_ramesh", "res123", "Rameshwar Gurjar", "+919876543310", "Johari Bazar", w_johari, "Gali 4, Johari Bazar", 26.9195, 75.8235, 79, 1, "tin", 0, "", "Chronic dehydration history", "Mahesh (Son)", "+919876500020"),
            ("res_kamlesh", "res123", "Kamlesh Meena", "+919876543311", "Johari Bazar", w_johari, "Near Badi Chaupar", 26.9210, 75.8250, 48, 0, "tin", 1, "Stone artisan / labour", "", "Gauri (Wife)", "+919876500021"),
            ("res_badri", "res123", "Badri Narayan", "+919876543312", "C-Scheme", w_cscheme, "Sector 3, C-Scheme", 26.9110, 75.7990, 82, 1, "concrete", 0, "", "Cardiac pacemaker", "Dr. Sharma", "+919876500022"),
            ("res_manju", "res123", "Manju Devi", "+919876543313", "Mansarovar", w_mansarovar, "Plot 11, Mansarovar", 26.8560, 75.7660, 67, 0, "asbestos", 0, "", "Diabetic", "Sanjay (Son)", "+919876500023")
        ]
        for uname, pwd, name, phone, w_name, w_idx, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone in j_residents:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'resident', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, j_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO households (user_id, city_id, ward_id, ward, address, latitude, longitude, age, is_living_alone, roof_type, is_outdoor_worker, job_type, medical_needs, emergency_contact_name, emergency_contact_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (u_id, j_id, w_idx, w_name, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone))

        # Cooling Points Jaipur
        j_cool = [
            ("Johari Bazar Public Jal Mandir", "water_kiosk", "Johari Bazar", w_johari, "Badi Chaupar, Jaipur", 26.9200, 75.8240, 250, 90, 1),
            ("SMS Hospital Heat Emergency Cell", "hospital", "C-Scheme", w_cscheme, "Jawahar Lal Nehru Marg", 26.9010, 75.8150, 50, 12, 1),
            ("Mansarovar Community Cool Shelter", "shelter", "Mansarovar", w_mansarovar, "Mansarovar Sector 7 Park", 26.8550, 75.7650, 100, 30, 1)
        ]
        for name, ptype, w_name, w_idx, addr, lat, lon, cap, occ, is_o in j_cool:
            cursor.execute("""
                INSERT INTO cooling_points (city_id, ward_id, name, point_type, ward, address, latitude, longitude, capacity, occupancy, is_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (j_id, w_idx, name, ptype, w_name, addr, lat, lon, cap, occ, is_o))

        # Alert Jaipur
        cursor.execute("""
            INSERT INTO alerts (city_id, title, message, target_ward, heat_level, dispatch_status)
            VALUES (?, 'Jaipur Desert Heat Advisory', 'Afternoon temperatures expected to exceed 43°C. Avoid outdoor travel between 12:00 PM and 4:00 PM.', 'All', 'Red', 'simulated')
        """, (j_id,))

        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'demo_mode', 'auto')", (j_id,))
        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'simulate_cutoff', '0')", (j_id,))

    # Past check-ins and visits so charts and activity are not empty
    today = date.today()
    cursor.execute("SELECT id FROM households")
    all_hh_ids = [row[0] for row in cursor.fetchall()]

    for days_back in range(5, 0, -1):
        past_d = today - timedelta(days=days_back)
        for h_id in all_hh_ids[:8]:
            cursor.execute("""
                INSERT OR IGNORE INTO check_ins (household_id, check_date, checked_at, status)
                VALUES (?, ?, ?, 'okay')
            """, (h_id, str(past_d), f"{past_d} 09:30:00"))

    cursor.execute("SELECT id FROM volunteers LIMIT 1")
    v_row = cursor.fetchone()
    if v_row:
        v_id = v_row[0]
        for past_h in all_hh_ids[:3]:
            cursor.execute("""
                INSERT INTO visits (volunteer_id, household_id, visit_date, status, supplies_given, notes)
                VALUES (?, ?, ?, 'checked', 'ors', 'Resident checked, resting in shaded room.')
            """, (v_id, past_h, str(today - timedelta(days=1))))

    # Global Settings
    cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (0, 'demo_mode', 'auto')")
    cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (0, 'simulate_cutoff', '0')")

    conn.commit()
    conn.close()

    if pass_level >= 2:
        seed_pass2_cities()

def seed_pass2_cities():
    """Seed additional demo cities for PASS 2: Chennai (Coastal), Kolkata (Coastal), Shimla (Hill)."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    def find_city(name):
        cursor.execute("SELECT id, name, climate_zone, latitude, longitude FROM locations WHERE type = 'city' AND name = ?", (name,))
        return cursor.fetchone()

    def get_or_create_ward(city_id, ward_name, lat, lon):
        cursor.execute("SELECT id FROM locations WHERE type = 'ward' AND parent_id = ? AND name = ?", (city_id, ward_name))
        row = cursor.fetchone()
        if row:
            return row[0]
        return add_ward(conn, city_id, ward_name, lat, lon)

    # Check if Chennai admin already exists
    cursor.execute("SELECT id FROM users WHERE username = 'admin_chennai'")
    if cursor.fetchone():
        conn.close()
        return

    # ========================================================
    # DEMO CITY 3: CHENNAI (Tamil Nadu - Coastal)
    # ========================================================
    chennai = find_city("Chennai")
    if chennai:
        c_id = chennai["id"]
        w_tnagar = get_or_create_ward(c_id, "T. Nagar", 13.0418, 80.2341)
        w_mylapore = get_or_create_ward(c_id, "Mylapore", 13.0368, 80.2676)
        w_royapuram = get_or_create_ward(c_id, "Royapuram", 13.1137, 80.2954)

        cursor.execute("""
            INSERT INTO users (username, password_hash, role, name, phone, city_id)
            VALUES ('admin_chennai', ?, 'admin', 'Greater Chennai Corporation Officer', '+919876543400', ?)
        """, (generate_password_hash("admin123"), c_id))

        c_vols = [
            ("vol_karthik", "vol123", "Karthik Subramanian", "+919876543401", "T. Nagar", w_tnagar, 13.0420, 80.2345),
            ("vol_meena", "vol123", "Meena Natarajan", "+919876543402", "Mylapore", w_mylapore, 13.0370, 80.2680)
        ]
        for uname, pwd, name, phone, w_name, w_idx, vlat, vlon in c_vols:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'volunteer', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, c_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO volunteers (user_id, city_id, ward_id, ward, base_latitude, base_longitude, badges)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (u_id, c_id, w_idx, w_name, vlat, vlon, '["First Responder"]'))

        c_residents = [
            ("res_murugan", "res123", "Murugan Velu", "+919876543410", "Royapuram", w_royapuram, "Harbour Slum Quarter, Royapuram", 13.1140, 80.2950, 77, 1, "tin", 0, "", "Cardiovascular weakness", "Selvi (Daughter)", "+919876500030"),
            ("res_lakshmi", "res123", "Lakshmi Ammal", "+919876543411", "T. Nagar", w_tnagar, "Usman Road Vendor Shed", 13.0410, 80.2335, 52, 0, "tin", 1, "Platform flower vendor", "Hypertension", "Ravi (Son)", "+919876500031"),
            ("res_selvam", "res123", "Selvam R.", "+919876543412", "Mylapore", w_mylapore, "Near Tank Street, Mylapore", 13.0360, 80.2670, 80, 1, "concrete", 0, "", "Respiratory distress", "Dr. Vasanth", "+919876500032"),
            ("res_anand", "res123", "Anand Kumar", "+919876543413", "T. Nagar", w_tnagar, "Ranganathan Street 12", 13.0425, 80.2350, 66, 0, "asbestos", 0, "", "Diabetic", "Geetha (Wife)", "+919876500033")
        ]
        for uname, pwd, name, phone, w_name, w_idx, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone in c_residents:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'resident', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, c_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO households (user_id, city_id, ward_id, ward, address, latitude, longitude, age, is_living_alone, roof_type, is_outdoor_worker, job_type, medical_needs, emergency_contact_name, emergency_contact_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (u_id, c_id, w_idx, w_name, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone))

        c_cool = [
            ("Royapuram Coastal Workers Jal Kiosk", "water_kiosk", "Royapuram", w_royapuram, "Royapuram Harbour Gate", 13.1135, 80.2955, 300, 140, 1),
            ("T. Nagar Municipal Community Hall", "shelter", "T. Nagar", w_tnagar, "Near Usman Road Park", 13.0415, 80.2340, 120, 35, 1),
            ("Rajiv Gandhi Govt General Hospital", "hospital", "Mylapore", w_mylapore, "EVR Periyar Salai", 13.0380, 80.2690, 80, 25, 1)
        ]
        for name, ptype, w_name, w_idx, addr, lat, lon, cap, occ, is_o in c_cool:
            cursor.execute("""
                INSERT INTO cooling_points (city_id, ward_id, name, point_type, ward, address, latitude, longitude, capacity, occupancy, is_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (c_id, w_idx, name, ptype, w_name, addr, lat, lon, cap, occ, is_o))

        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'demo_mode', 'auto')", (c_id,))
        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'simulate_cutoff', '0')", (c_id,))

    # ========================================================
    # DEMO CITY 4: KOLKATA (West Bengal - Coastal)
    # ========================================================
    kolkata = find_city("Kolkata")
    if kolkata:
        k_id = kolkata["id"]
        w_park = get_or_create_ward(k_id, "Park Street", 22.5510, 88.3520)
        w_shyam = get_or_create_ward(k_id, "Shyambazar", 22.6020, 88.3710)
        w_howrah = get_or_create_ward(k_id, "Howrah Station Area", 22.5850, 88.3420)

        cursor.execute("""
            INSERT INTO users (username, password_hash, role, name, phone, city_id)
            VALUES ('admin_kolkata', ?, 'admin', 'Kolkata Municipal Corporation Officer', '+919876543500', ?)
        """, (generate_password_hash("admin123"), k_id))

        k_vols = [
            ("vol_sourav", "vol123", "Sourav Mukherjee", "+919876543501", "Shyambazar", w_shyam, 22.6025, 88.3715),
            ("vol_debi", "vol123", "Debjani Bose", "+919876543502", "Park Street", w_park, 22.5515, 88.3525)
        ]
        for uname, pwd, name, phone, w_name, w_idx, vlat, vlon in k_vols:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'volunteer', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, k_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO volunteers (user_id, city_id, ward_id, ward, base_latitude, base_longitude, badges)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (u_id, k_id, w_idx, w_name, vlat, vlon, '["First Responder"]'))

        k_residents = [
            ("res_subhash", "res123", "Subhash Chandra Pal", "+919876543510", "Shyambazar", w_shyam, "Raja Dinendra Street 14", 22.6015, 88.3705, 82, 1, "tin", 0, "", "Chronic renal illness", "Bikram (Son)", "+919876500040"),
            ("res_pratima", "res123", "Pratima Das", "+919876543511", "Howrah Station Area", w_howrah, "Coolie Barracks, Station Road", 22.5845, 88.3415, 49, 0, "tin", 1, "Head-load porter", "", "Gopal (Brother)", "+919876500041"),
            ("res_bimal", "res123", "Bimal Ghosh", "+919876543512", "Park Street", w_park, "Rowdon Street Colony", 22.5505, 88.3515, 75, 1, "concrete", 0, "", "Asthma", "Tapas (Nephew)", "+919876500042"),
            ("res_arati", "res123", "Arati Roy", "+919876543513", "Shyambazar", w_shyam, "Bidhan Sarani 88", 22.6030, 88.3720, 68, 0, "asbestos", 0, "", "Hypertension", "Rina (Daughter)", "+919876500043")
        ]
        for uname, pwd, name, phone, w_name, w_idx, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone in k_residents:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'resident', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, k_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO households (user_id, city_id, ward_id, ward, address, latitude, longitude, age, is_living_alone, roof_type, is_outdoor_worker, job_type, medical_needs, emergency_contact_name, emergency_contact_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (u_id, k_id, w_idx, w_name, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone))

        k_cool = [
            ("Shyambazar Five-Point Jal Chhatra", "water_kiosk", "Shyambazar", w_shyam, "Shyambazar Crossing", 22.6020, 88.3710, 200, 75, 1),
            ("Howrah Station Shaded Cooling Kiosk", "shelter", "Howrah Station Area", w_howrah, "Station Forecourt", 22.5850, 88.3420, 150, 60, 1),
            ("Calcutta National Medical College Cold Unit", "hospital", "Park Street", w_park, "Gorachand Road", 22.5490, 88.3530, 60, 18, 1)
        ]
        for name, ptype, w_name, w_idx, addr, lat, lon, cap, occ, is_o in k_cool:
            cursor.execute("""
                INSERT INTO cooling_points (city_id, ward_id, name, point_type, ward, address, latitude, longitude, capacity, occupancy, is_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (k_id, w_idx, name, ptype, w_name, addr, lat, lon, cap, occ, is_o))

        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'demo_mode', 'auto')", (k_id,))
        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'simulate_cutoff', '0')", (k_id,))

    # ========================================================
    # DEMO CITY 5: SHIMLA (Himachal Pradesh - Hill)
    # ========================================================
    shimla = find_city("Shimla")
    if shimla:
        s_id = shimla["id"]
        w_mall = get_or_create_ward(s_id, "Mall Road", 31.1045, 77.1740)
        w_sanjauli = get_or_create_ward(s_id, "Sanjauli", 31.1010, 77.1950)
        w_chotta = get_or_create_ward(s_id, "Chotta Shimla", 31.0920, 77.1810)

        cursor.execute("""
            INSERT INTO users (username, password_hash, role, name, phone, city_id)
            VALUES ('admin_shimla', ?, 'admin', 'Shimla Municipal Corporation Officer', '+919876543600', ?)
        """, (generate_password_hash("admin123"), s_id))

        s_vols = [
            ("vol_rohit", "vol123", "Rohit Verma", "+919876543601", "Mall Road", w_mall, 31.1048, 77.1745),
            ("vol_anjali", "vol123", "Anjali Thakur", "+919876543602", "Sanjauli", w_sanjauli, 31.1015, 77.1955)
        ]
        for uname, pwd, name, phone, w_name, w_idx, vlat, vlon in s_vols:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'volunteer', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, s_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO volunteers (user_id, city_id, ward_id, ward, base_latitude, base_longitude, badges)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (u_id, s_id, w_idx, w_name, vlat, vlon, '["First Responder"]'))

        s_residents = [
            ("res_bhagat", "res123", "Bhagat Ram Sharma", "+919876543610", "Sanjauli", w_sanjauli, "Steep Ridge Path, Sanjauli", 31.1005, 77.1945, 81, 1, "tin", 0, "", "Cardiac bypass & steep stair fatigue", "Pankaj (Son)", "+919876500050"),
            ("res_vidya", "res123", "Vidya Devi", "+919876543611", "Mall Road", w_mall, "Lakkar Bazar Lower Steps", 31.1050, 77.1735, 76, 1, "thatched", 0, "", "Joint arthritis", "Sushma (Daughter)", "+919876500051"),
            ("res_mohan_singh", "res123", "Mohan Singh", "+919876543612", "Sanjauli", w_sanjauli, "Cemetery Road, Sanjauli", 31.1020, 77.1960, 55, 0, "tin", 1, "Hill cargo porter", "", "Champa (Wife)", "+919876500052"),
            ("res_kamla_devi", "res123", "Kamla Devi Negi", "+919876543613", "Chotta Shimla", w_chotta, "Near Secretariat Gate", 31.0925, 77.1815, 70, 0, "concrete", 0, "", "Hypertension", "Rakesh (Son)", "+919876500053")
        ]
        for uname, pwd, name, phone, w_name, w_idx, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone in s_residents:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, phone, city_id)
                VALUES (?, ?, 'resident', ?, ?, ?)
            """, (uname, generate_password_hash(pwd), name, phone, s_id))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO households (user_id, city_id, ward_id, ward, address, latitude, longitude, age, is_living_alone, roof_type, is_outdoor_worker, job_type, medical_needs, emergency_contact_name, emergency_contact_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (u_id, s_id, w_idx, w_name, addr, lat, lon, age, alone, roof, outdoor, job, med, ec_name, ec_phone))

        s_cool = [
            ("Sanjauli Community Shade Centre", "shelter", "Sanjauli", w_sanjauli, "Sanjauli Bazar Complex", 31.1010, 77.1950, 80, 20, 1),
            ("Ridge Public Natural Spring Jal Point", "water_kiosk", "Mall Road", w_mall, "The Ridge, Near Church", 31.1045, 77.1740, 150, 45, 1),
            ("Indira Gandhi Medical College (IGMC)", "hospital", "Chotta Shimla", w_chotta, "Circular Road, Shimla", 31.0930, 77.1820, 50, 10, 1)
        ]
        for name, ptype, w_name, w_idx, addr, lat, lon, cap, occ, is_o in s_cool:
            cursor.execute("""
                INSERT INTO cooling_points (city_id, ward_id, name, point_type, ward, address, latitude, longitude, capacity, occupancy, is_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (s_id, w_idx, name, ptype, w_name, addr, lat, lon, cap, occ, is_o))

        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'demo_mode', 'auto')", (s_id,))
        cursor.execute("INSERT OR REPLACE INTO settings (city_id, key, value) VALUES (?, 'simulate_cutoff', '0')", (s_id,))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    seed_db(pass_level=1)
    print("HeatShield database initialized and seeded successfully for All-India scope.")
