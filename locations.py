import json
import os
import sqlite3

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "india_cities.json")

def load_cities_json():
    """Load reference cities list from data/india_cities.json."""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def sync_locations_to_db(conn):
    """Ensure all states and cities from india_cities.json are stored in locations table."""
    cursor = conn.cursor()
    cities = load_cities_json()

    for item in cities:
        state_name = item.get("state")
        city_name = item.get("name")
        lat = item.get("latitude")
        lon = item.get("longitude")
        zone = item.get("climate_zone", "plains")

        # 1. Ensure state entry exists
        cursor.execute("SELECT id FROM locations WHERE type = 'state' AND name = ?", (state_name,))
        state_row = cursor.fetchone()
        if state_row:
            state_id = state_row[0]
        else:
            cursor.execute("""
                INSERT INTO locations (type, name, parent_id, latitude, longitude, climate_zone)
                VALUES ('state', ?, NULL, ?, ?, ?)
            """, (state_name, lat, lon, zone))
            state_id = cursor.lastrowid

        # 2. Ensure city entry exists
        cursor.execute("SELECT id FROM locations WHERE type = 'city' AND name = ? AND parent_id = ?", (city_name, state_id))
        city_row = cursor.fetchone()
        if not city_row:
            cursor.execute("""
                INSERT INTO locations (type, name, parent_id, latitude, longitude, climate_zone)
                VALUES ('city', ?, ?, ?, ?, ?)
            """, (city_name, state_id, lat, lon, zone))

    conn.commit()

def get_all_states(conn):
    """Return all states ordered by name."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM locations WHERE type = 'state' ORDER BY name ASC")
    return cursor.fetchall()

def get_cities_by_state(conn, state_name_or_id):
    """Return cities belonging to a state by its name or ID."""
    cursor = conn.cursor()
    if isinstance(state_name_or_id, int) or (isinstance(state_name_or_id, str) and state_name_or_id.isdigit()):
        cursor.execute("""
            SELECT id, name, latitude, longitude, climate_zone
            FROM locations
            WHERE type = 'city' AND parent_id = ?
            ORDER BY name ASC
        """, (int(state_name_or_id),))
    else:
        cursor.execute("""
            SELECT c.id, c.name, c.latitude, c.longitude, c.climate_zone
            FROM locations c
            JOIN locations s ON c.parent_id = s.id
            WHERE c.type = 'city' AND s.name = ?
            ORDER BY c.name ASC
        """, (state_name_or_id,))
    return cursor.fetchall()

def get_city_by_id(conn, city_id):
    """Fetch single city location record with state name."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.name, c.parent_id, c.latitude, c.longitude, c.climate_zone, s.name as state_name
        FROM locations c
        LEFT JOIN locations s ON c.parent_id = s.id
        WHERE c.type = 'city' AND c.id = ?
    """, (city_id,))
    return cursor.fetchone()

def get_wards_by_city(conn, city_id):
    """Fetch all wards configured for a city."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, latitude, longitude, climate_zone
        FROM locations
        WHERE type = 'ward' AND parent_id = ?
        ORDER BY name ASC
    """, (city_id,))
    return cursor.fetchall()

def add_ward(conn, city_id, ward_name, latitude, longitude):
    """Add a new municipal ward to a city."""
    cursor = conn.cursor()
    # inherit climate_zone from city
    city = get_city_by_id(conn, city_id)
    zone = city["climate_zone"] if city else "plains"
    cursor.execute("""
        INSERT INTO locations (type, name, parent_id, latitude, longitude, climate_zone)
        VALUES ('ward', ?, ?, ?, ?, ?)
    """, (ward_name, city_id, latitude, longitude, zone))
    conn.commit()
    return cursor.lastrowid

def add_city(conn, state_name, city_name, latitude, longitude, climate_zone="plains"):
    """Add a new city under a state (creating state if necessary)."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM locations WHERE type = 'state' AND name = ?", (state_name,))
    state_row = cursor.fetchone()
    if state_row:
        state_id = state_row[0]
    else:
        cursor.execute("""
            INSERT INTO locations (type, name, parent_id, latitude, longitude, climate_zone)
            VALUES ('state', ?, NULL, ?, ?, ?)
        """, (state_name, latitude, longitude, climate_zone))
        state_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO locations (type, name, parent_id, latitude, longitude, climate_zone)
        VALUES ('city', ?, ?, ?, ?, ?)
    """, (city_name, state_id, latitude, longitude, climate_zone))
    conn.commit()
    return cursor.lastrowid
