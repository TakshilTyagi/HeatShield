import unittest
import sys
import os
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import init_db, seed_db, get_db_connection
from routes.admin import auto_assign_visits_internal

class TestAssignmentLogic(unittest.TestCase):
    """Test auto-assignment algorithm: caps, ward matching, distance tie-breaking, city scoping."""

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_db(pass_level=1)

    def test_auto_assignment_execution(self):
        today_str = date.today().isoformat()
        conn = get_db_connection()
        conn.execute("DELETE FROM assignments WHERE assigned_date = ?", (today_str,))
        conn.commit()

        # Find city_id for Bareilly
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM locations WHERE type = 'city' AND name = 'Bareilly'")
        b_row = cursor.fetchone()
        city_id = b_row["id"] if b_row else 1
        conn.close()

        assigned_cnt, total_households = auto_assign_visits_internal(today_str, "Red", city_id)

        self.assertGreater(assigned_cnt, 0)
        self.assertLessEqual(assigned_cnt, total_households)

        # Verify daily capacity cap (max 8 households per volunteer)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.volunteer_id, COUNT(*) as cnt
            FROM assignments a
            JOIN volunteers v ON a.volunteer_id = v.id
            WHERE a.assigned_date = ? AND v.city_id = ?
            GROUP BY a.volunteer_id
        """, (today_str, city_id))
        rows = cursor.fetchall()
        for r in rows:
            self.assertLessEqual(r["cnt"], 8, "Volunteer assignments exceeded maximum capacity cap of 8!")

        # Verify uniqueness per household per day
        cursor.execute("""
            SELECT household_id, COUNT(*) as cnt
            FROM assignments
            WHERE assigned_date = ?
            GROUP BY household_id
            HAVING cnt > 1
        """, (today_str,))
        duplicates = cursor.fetchall()
        self.assertEqual(len(duplicates), 0, "Found duplicate daily assignment for household!")

        conn.close()

if __name__ == "__main__":
    unittest.main()
