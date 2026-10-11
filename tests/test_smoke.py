import unittest
import sys
import os
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from database import init_db, seed_db, get_db_connection
from config import Config

class TestSmokeAndFlow(unittest.TestCase):
    """
    Smoke tests and complete 5-step demo workflow verification:
    - Login for each role (super_admin, admin, volunteer, resident)
    - Role-based access redirects
    - Check-in submission and SOS beacon
    - 5-step demo scenario execution
    - Daily heat check API with token
    """

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_db(pass_level=1)
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_public_pages(self):
        # / must redirect directly to /login
        resp_root = self.client.get("/")
        self.assertEqual(resp_root.status_code, 302)
        self.assertIn("/login", resp_root.headers["Location"])

        # Following redirect opens the login page directly
        resp_follow = self.client.get("/", follow_redirects=True)
        self.assertEqual(resp_follow.status_code, 200)
        self.assertIn(b"HeatShield", resp_follow.data)
        self.assertIn(b"Sign In", resp_follow.data)

        resp_login = self.client.get("/login")
        self.assertEqual(resp_login.status_code, 200)

        resp_about = self.client.get("/about")
        self.assertEqual(resp_about.status_code, 200)

        resp_register = self.client.get("/register")
        self.assertEqual(resp_register.status_code, 200)

    def test_role_based_access_redirect(self):
        fresh_client = self.app.test_client()
        resp = fresh_client.get("/admin/dashboard")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_super_admin_flow(self):
        client = self.app.test_client()
        resp_login = client.post("/login", data={"username": "superadmin", "password": "admin123"}, follow_redirects=True)
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn(b"Pan-India Heatwave Control Center", resp_login.data)

        resp_super = client.get("/admin/super")
        self.assertEqual(resp_super.status_code, 200)
        self.assertIn(b"Monitored Cities", resp_super.data)

    def test_resident_flow(self):
        client = self.app.test_client()
        # Login as res_shanti
        resp = client.post("/login", data={"username": "res_shanti", "password": "res123"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Resident Dashboard", resp.data)

        # Attempt to access admin dashboard with resident account -> Access Denied
        resp_admin = client.get("/admin/dashboard", follow_redirects=True)
        self.assertEqual(resp_admin.status_code, 200)
        self.assertIn(b"Access denied", resp_admin.data)

        # Submit "I'm okay" check-in
        resp_checkin = client.post("/resident/checkin", follow_redirects=True)
        self.assertEqual(resp_checkin.status_code, 200)

        # Trigger SOS
        resp_sos = client.post("/resident/sos", follow_redirects=True)
        self.assertEqual(resp_sos.status_code, 200)
        self.assertTrue(b"EMERGENCY BEACON ACTIVE" in resp_sos.data or b"ACTIVE SOS EMERGENCY BEACON" in resp_sos.data)

    def test_volunteer_flow(self):
        client = self.app.test_client()
        resp = client.post("/login", data={"username": "vol_amit", "password": "vol123"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Assigned Visits", resp.data)

        resp_act = client.get("/volunteer/activity")
        self.assertEqual(resp_act.status_code, 200)

    def test_admin_flow(self):
        client = self.app.test_client()
        resp = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Ward Operations Control", resp.data)

        resp_hh = client.get("/admin/households")
        self.assertEqual(resp_hh.status_code, 200)

        resp_sos = client.get("/admin/sos-cases")
        self.assertEqual(resp_sos.status_code, 200)

        resp_cool = client.get("/admin/cooling-centres")
        self.assertEqual(resp_cool.status_code, 200)

        resp_rep = client.get("/admin/reports")
        self.assertEqual(resp_rep.status_code, 200)

        resp_csv = client.get("/admin/reports/download-csv")
        self.assertEqual(resp_csv.status_code, 200)
        self.assertEqual(resp_csv.content_type, "text/csv; charset=utf-8")

    def test_five_step_demo_flow(self):
        """
        Executes the exact 5-step hackathon demo flow:
        1. Admin turns Demo mode to Red. Level changes, alert dispatched, visits auto-assigned.
        2. One resident logs in and taps 'I'm okay'. Another resident does not check in.
        3. Admin presses 'Simulate 12:00 cutoff'. Missed resident moves to top of volunteer list.
        4. Volunteer visits and marks 'Needs help', logging supplies given.
        5. Admin dashboard updates (counts, needs-help list) and admin resolves or sends alert.
        """
        today_str = date.today().isoformat()
        admin_c = self.app.test_client()
        res_ok_c = self.app.test_client()
        vol_c = self.app.test_client()

        # Step 1: Admin logs in and turns Demo mode to Red
        admin_c.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
        resp_step1 = admin_c.post("/admin/set-demo-mode", data={"demo_mode": "Red"}, follow_redirects=True)
        self.assertEqual(resp_step1.status_code, 200)
        self.assertIn(b"RED", resp_step1.data)

        # Step 2: One resident logs in and checks in ("I'm okay"). (res_shanti checks in, res_ram does not)
        res_ok_c.post("/login", data={"username": "res_shanti", "password": "res123"}, follow_redirects=True)
        resp_step2 = res_ok_c.post("/resident/checkin", follow_redirects=True)
        self.assertEqual(resp_step2.status_code, 200)

        # Step 3: Admin activates 12:00 cutoff simulation
        resp_step3 = admin_c.post("/admin/toggle-cutoff", follow_redirects=True)
        self.assertEqual(resp_step3.status_code, 200)

        # Step 4: Volunteer logs in, sees unchecked high-risk resident at top, marks 'Needs help'
        vol_c.post("/login", data={"username": "vol_amit", "password": "vol123"}, follow_redirects=True)
        resp_visits = vol_c.get("/volunteer/visits")
        self.assertEqual(resp_visits.status_code, 200)

        # Volunteer logs visit for Ram Prasad
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM households WHERE address LIKE '%House 14%'")
        ram_h = cursor.fetchone()
        self.assertIsNotNone(ram_h)
        ram_id = ram_h[0]

        cursor.execute("SELECT id FROM assignments WHERE household_id = ? AND assigned_date = ?", (ram_id, today_str))
        asg = cursor.fetchone()
        asg_id = asg[0] if asg else 1
        conn.close()

        resp_visit_submit = vol_c.post("/volunteer/record-visit", data={
            "household_id": ram_id,
            "assignment_id": asg_id,
            "status": "needs_help",
            "supplies_given": "ors_water",
            "notes": "Elderly resident experiencing dizziness, administered ORS and notified desk."
        }, follow_redirects=True)
        self.assertEqual(resp_visit_submit.status_code, 200)

        # Step 5: Admin dashboard reflects open needs-help / SOS cases and resolves
        resp_admin_check = admin_c.get("/admin/dashboard")
        self.assertEqual(resp_admin_check.status_code, 200)

        # Admin resolves SOS case
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sos_alerts WHERE household_id = ? AND is_resolved = 0", (ram_id,))
        open_sos = cursor.fetchone()
        self.assertIsNotNone(open_sos)
        sos_id = open_sos[0]
        conn.close()

        resp_resolve = admin_c.post("/admin/resolve-sos", data={
            "sos_id": sos_id,
            "notes": "Emergency mobile unit dispatched with saline hydration."
        }, follow_redirects=True)
        self.assertEqual(resp_resolve.status_code, 200)

    def test_daily_heat_check_api(self):
        resp_unauth = self.client.post("/api/daily-heat-check")
        self.assertEqual(resp_unauth.status_code, 401)

        headers = {"X-Heat-Token": Config.HEAT_CHECK_TOKEN}
        resp_auth = self.client.post("/api/daily-heat-check", headers=headers)
        self.assertEqual(resp_auth.status_code, 200)
        json_data = resp_auth.get_json()
        self.assertEqual(json_data["status"], "success")
        self.assertIn("cities_processed", json_data)

if __name__ == "__main__":
    unittest.main()
