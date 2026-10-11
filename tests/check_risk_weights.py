import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import get_db_connection, init_db, seed_db
from risk import calculate_household_risk

def check_risk_weights():
    init_db()
    seed_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT h.id, u.name, h.age, h.is_living_alone, h.roof_type, h.is_outdoor_worker, 
               h.job_type, h.medical_needs, h.ward
        FROM households h
        JOIN users u ON h.user_id = u.id
    """)
    households = cursor.fetchall()
    conn.close()

    scored = []
    for h in households:
        h_dict = dict(h)
        # Score under simulated Red heatwave day with no check-in yet, no open SOS
        res = calculate_household_risk(h_dict, day_level="Red", has_checked_in_today=False, has_open_sos=False)
        scored.append((res["score"], h_dict["name"], h_dict["age"], h_dict["roof_type"], h_dict["is_living_alone"], res["reasons"]))

    # Sort descending
    scored.sort(key=lambda x: x[0], reverse=True)

    print("=================================================================")
    print("HEATSHIELD RISK WEIGHT TUNING & RANKING VERIFICATION (15 RESIDENTS)")
    print("=================================================================")
    for rank, (score, name, age, roof, alone, reasons) in enumerate(scored, 1):
        alone_str = "Alone" if alone else "With family"
        print(f"Rank {rank:2d}: Score {score:3d} | {name:<18} (Age {age:2d}, {roof:<8} roof, {alone_str})")
        print(f"         Reasons: {', '.join(reasons[:3])}")

    # Explicit check: 78-year-old living alone under tin roof must outrank younger concrete home
    ram_score = next(s[0] for s in scored if "Ram Prasad" in s[1])
    mukesh_score = next(s[0] for s in scored if "Mukesh Yadav" in s[1])

    print("\n-----------------------------------------------------------------")
    print(f"Verification Check: Ram Prasad (Score: {ram_score}) vs Mukesh Yadav (Score: {mukesh_score})")
    assert ram_score > mukesh_score, "ERROR: Ram Prasad must outrank Mukesh Yadav!"
    print("RESULT: PASS - Explainable risk scoring successfully ranks vulnerable seniors at top.")
    print("=================================================================")

if __name__ == "__main__":
    check_risk_weights()
