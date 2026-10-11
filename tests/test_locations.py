import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import init_db, seed_db, get_db_connection
from locations import load_cities_json, get_all_states, get_cities_by_state, get_wards_by_city, get_city_by_id

class TestLocationsAndIsolation(unittest.TestCase):
    """Test locations hierarchy, json parsing, and strict cross-city data isolation."""

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_db(pass_level=1)

    def test_cities_json_dataset(self):
        cities = load_cities_json()
        self.assertGreaterEqual(len(cities), 40, "Dataset must contain at least 40 major cities")
        
        states = {c.get("state") for c in cities if c.get("state")}
        self.assertGreaterEqual(len(states), 20, "Dataset must cover at least 20 Indian states and union territories")

        # Verify climate zones
        zones = {c.get("climate_zone") for c in cities}
        self.assertTrue({"plains", "coastal", "hill"}.issubset(zones), "All three climate zones must be represented")

    def test_location_helpers(self):
        conn = get_db_connection()
        states = get_all_states(conn)
        self.assertGreater(len(states), 0)

        # Check Bareilly lookup
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM locations WHERE type = 'city' AND name = 'Bareilly'")
        b_id = cursor.fetchone()[0]

        city = get_city_by_id(conn, b_id)
        self.assertEqual(city["name"], "Bareilly")
        self.assertEqual(city["climate_zone"], "plains")

        wards = get_wards_by_city(conn, b_id)
        self.assertGreaterEqual(len(wards), 5, "Bareilly should have seeded municipal wards")
        conn.close()

    def test_cross_city_data_isolation(self):
        """Verify city A cannot access, see, or reassign city B's households or volunteers."""
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get Bareilly and Jaipur city IDs
        cursor.execute("SELECT id FROM locations WHERE type = 'city' AND name = 'Bareilly'")
        b_id = cursor.fetchone()[0]

        cursor.execute("SELECT id FROM locations WHERE type = 'city' AND name = 'Jaipur'")
        j_id = cursor.fetchone()[0]

        self.assertNotEqual(b_id, j_id)

        # 1. Households isolation
        cursor.execute("SELECT id FROM households WHERE city_id = ?", (b_id,))
        b_hh = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT id FROM households WHERE city_id = ?", (j_id,))
        j_hh = {row[0] for row in cursor.fetchall()}

        self.assertTrue(len(b_hh) > 0 and len(j_hh) > 0)
        self.assertEqual(len(b_hh.intersection(j_hh)), 0, "Households must be strictly partitioned by city_id")

        # 2. Volunteers isolation
        cursor.execute("SELECT id FROM volunteers WHERE city_id = ?", (b_id,))
        b_vols = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT id FROM volunteers WHERE city_id = ?", (j_id,))
        j_vols = {row[0] for row in cursor.fetchall()}

        self.assertTrue(len(b_vols) > 0 and len(j_vols) > 0)
        self.assertEqual(len(b_vols.intersection(j_vols)), 0, "Volunteers must be strictly partitioned by city_id")

        # 3. Cooling points isolation
        cursor.execute("SELECT id FROM cooling_points WHERE city_id = ?", (b_id,))
        b_cp = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT id FROM cooling_points WHERE city_id = ?", (j_id,))
        j_cp = {row[0] for row in cursor.fetchall()}

        self.assertEqual(len(b_cp.intersection(j_cp)), 0, "Cooling points must be strictly partitioned by city_id")

        conn.close()

if __name__ == "__main__":
    unittest.main()
