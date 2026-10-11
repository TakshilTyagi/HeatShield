import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from risk import calculate_heat_index, get_heat_level, calculate_household_risk, calculate_3day_outlook

class TestRiskLogic(unittest.TestCase):
    """Test every scoring rule, Rothfusz conversion, day thresholds, and 12:00 cutoff rule."""

    def test_heat_index_rothfusz(self):
        # 40 C and 50% relative humidity should give extreme heat index (>45 C)
        hi = calculate_heat_index(40.0, 50.0)
        self.assertGreater(hi, 45.0)

        # Mild temperature (20 C) should bypass extreme Rothfusz equation and stay low
        hi_mild = calculate_heat_index(20.0, 50.0)
        self.assertLess(hi_mild, 30.0)

    def test_heat_day_levels(self):
        # Green below 35 C for plains
        lvl_g, _, _ = get_heat_level(32.0, "plains")
        self.assertEqual(lvl_g, "Green")

        # Orange 35 C to 41 C for plains
        lvl_o, _, _ = get_heat_level(38.0, "plains")
        self.assertEqual(lvl_o, "Orange")

        # Red above 41 C for plains
        lvl_r, _, _ = get_heat_level(43.0, "plains")
        self.assertEqual(lvl_r, "Red")

    def test_per_climate_zone_thresholds(self):
        # Coastal: green < 33, orange 33-38, red > 38
        self.assertEqual(get_heat_level(32.0, "coastal")[0], "Green")
        self.assertEqual(get_heat_level(35.0, "coastal")[0], "Orange")
        self.assertEqual(get_heat_level(39.0, "coastal")[0], "Red")

        # Hill: green < 26, orange 26-30, red > 30
        self.assertEqual(get_heat_level(25.0, "hill")[0], "Green")
        self.assertEqual(get_heat_level(28.0, "hill")[0], "Orange")
        self.assertEqual(get_heat_level(31.0, "hill")[0], "Red")

    def test_household_scoring_rules(self):
        # Case 1: 78-year-old living alone with tin roof and medical need on Red day with no check-in
        h1 = {
            "age": 78,              # +30
            "is_living_alone": 1,   # +20
            "roof_type": "tin",     # +15
            "is_outdoor_worker": 0,
            "medical_needs": "Hypertension" # +15
        }
        # Under Red day with no check-in (+20) -> 30 + 20 + 15 + 15 + 20 = 100
        res1 = calculate_household_risk(h1, day_level="Red", has_checked_in_today=False, has_open_sos=False)
        self.assertEqual(res1["score"], 100)
        self.assertEqual(res1["category"], "Critical")
        self.assertTrue(res1["missed_cutoff"])

        # Case 2: 40-year-old living with family in concrete house with check-in
        h2 = {
            "age": 40,
            "is_living_alone": 0,
            "roof_type": "concrete",
            "is_outdoor_worker": 0,
            "medical_needs": ""
        }
        res2 = calculate_household_risk(h2, day_level="Red", has_checked_in_today=True, has_open_sos=False)
        self.assertEqual(res2["score"], 0)
        self.assertEqual(res2["category"], "Low")
        self.assertFalse(res2["missed_cutoff"])

    def test_twelve_pm_cutoff_rule(self):
        # Rule: on Orange/Red days, any household with score 60+ and no check-in by 12:00 is flagged "Missed check-in"
        h_borderline = {
            "age": 65,              # +25
            "is_living_alone": 1,   # +20
            "roof_type": "concrete",
            "is_outdoor_worker": 0,
            "medical_needs": ""
        }
        # On Green day: no check-in penalty, total = 45 -> score < 60 -> missed_cutoff is False
        res_green = calculate_household_risk(h_borderline, day_level="Green", has_checked_in_today=False, has_open_sos=False)
        self.assertFalse(res_green["missed_cutoff"])

        # On Red day: no check-in adds +20 -> total = 65 -> score >= 60 -> missed_cutoff is True
        res_red = calculate_household_risk(h_borderline, day_level="Red", has_checked_in_today=False, has_open_sos=False)
        self.assertEqual(res_red["score"], 65)
        self.assertTrue(res_red["missed_cutoff"])

    def test_3day_heat_outlook(self):
        forecast = [
            {"date": "2026-06-01", "temp_max": 40.0, "heat_index": 42.0},
            {"date": "2026-06-02", "temp_max": 42.0, "heat_index": 44.0},
            {"date": "2026-06-03", "temp_max": 43.5, "heat_index": 46.0}
        ]
        outlook = calculate_3day_outlook(forecast)
        self.assertEqual(outlook["trend"], "Hotter")
        self.assertEqual(outlook["red_days_count"], 3)

if __name__ == "__main__":
    unittest.main()
