# Team Notes & Engineering Log

This file tracks architectural decisions, verification findings, multi-city enhancements, and bug-resolution history across all engineering roles for both PASS 1 and PASS 2.

---

## Role 1: R&D Specialist
- **Actions:**
  - Researched and verified Rothfusz 9-term heat index polynomial regression equation, Steadman screening formula (<80°F), and low/high humidity edge adjustments from NOAA / NWS SR 90-23 technical memorandum.
  - Researched India Meteorological Department (IMD) official criteria for heatwaves across three distinct geographic domains:
    - Plains: Normal max temp $\ge 40^\circ\text{C}$; Heatwave departure $\ge +4.5^\circ\text{C}$ or actual $\ge 45^\circ\text{C}$.
    - Coastal: Normal max temp $\ge 37^\circ\text{C}$; Heatwave departure $\ge +4.5^\circ\text{C}$ or actual $\ge 37^\circ\text{C}$.
    - Hill: Normal max temp $\ge 30^\circ\text{C}$; Heatwave departure $\ge +4.5^\circ\text{C}$ or actual $\ge 30^\circ\text{C}$.
  - Grounded HeatShield's operational thresholds per climate zone in physiological distress thresholds:
    - Plains: Green $<35^\circ\text{C}$, Orange $35-41^\circ\text{C}$, Red $>41^\circ\text{C}$.
    - Coastal: Green $<33^\circ\text{C}$, Orange $33-38^\circ\text{C}$, Red $>38^\circ\text{C}$ (accommodating high humidity impairment of sweating).
    - Hill: Green $<26^\circ\text{C}$, Orange $26-30^\circ\text{C}$, Red $>30^\circ\text{C}$ (accommodating cold-insulated housing and unacclimatized population).
  - Verified Open-Meteo API specifications (`temperature_2m`, `relative_humidity_2m`, `apparent_temperature`, units in °C and %, 5.0-second timeout).
  - Selected and verified municipal coordinates for 5 Demo Cities across 4 regions and 3 climate zones:
    1. Bareilly (UP - Plains): `28.3667` N, `79.4317` E
    2. Jaipur (Rajasthan - Plains): `26.9124` N, `75.7873` E
    3. Chennai (Tamil Nadu - Coastal): `13.0827` N, `80.2707` E
    4. Kolkata (West Bengal - Coastal): `22.5726` N, `88.3639` E
    5. Shimla (Himachal Pradesh - Hill): `31.1048` N, `77.1734` E
  - Confirmed applicability of national emergency dispatch `112` pan-India, and ambulance service `108` in UP, Rajasthan, Tamil Nadu, and Himachal Pradesh.
- **Documents Created / Updated:**
  - `docs/RESEARCH.md`

---

## Role 2: UI/UX Designer
- **Actions:**
  - Designed accessible design tokens tailored to humanitarian operations and civil defense:
    - Palette: Archival paper `#FAF7F2`, Carbon `#1F1D1A`, Terracotta `#C2410C`, Green `#2F7D4F`, Amber `#D98A00`, Red `#B42318`.
    - Strict avoidance of purple/blue gradients, neon glow, emoji headings, or floating blobs.
    - Typography: `Source Serif 4` for authoritative headings, `Inter` for clean data tables and controls.
  - Wireframed multi-role user flows:
    - Elder residents: high text contrast, 1-tap "I'm okay" confirmation, high-contrast SOS button with 112/108 advisory.
    - Field volunteers: mobile-first, minimum 44px tap targets, high sunlight contrast cards, distance in km, risk breakdown chips.
    - Ward admins: dense tabular operations, real-time Leaflet heat map, Chart.js check-in bars, 3-day predictive outlook.
    - Super admins: nationwide surveillance grid, Leaflet map of India with colored city markers, global demo overrides.
  - Implemented bilingual UI layout supporting English and Hindi with instant toggle and session persistence.
- **Documents Created / Updated:**
  - `docs/DESIGN.md`

---

## Role 3: Backend Engineer
- **Actions:**
  - Architected SQLite schema using standard library `sqlite3` (no ORM) across 11 relational tables: `locations`, `users`, `households`, `volunteers`, `assignments`, `check_ins`, `visits`, `sos_alerts`, `cooling_points`, `alerts`, `settings`.
  - Enforced strict foreign keys, parameterized queries, and city partitioning (`city_id`) across all tables.
  - Built `locations.py` loading `data/india_cities.json` (42 major cities across >20 states/UTs) and syncing State > City > Ward hierarchy.
  - Built `weather.py` with in-memory 30-minute caching, 5-second timeout, and deterministic fallback per climate zone.
  - Built `aws_services.py` with Amazon SNS publisher and graceful fallback to `simulated` mode when credentials are missing.
  - Built `routes/auth.py` with cascade registration (State > City > Ward) and 10-digit Indian mobile validation.
  - Built `routes/resident.py`, `routes/volunteer.py`, and `routes/admin.py` with strict scoping by user `city_id`.
  - Added Super Admin overview (`/admin/super`) and administrative addition of cities and wards.
  - Built `routes/api.py` with location cascade endpoints and `/api/daily-heat-check` loop over active cities with `X-Heat-Token` security.
  - Implemented `lambda/heat_check_lambda.py` using standard `urllib` for EventBridge morning cron triggers.

---

## Role 4: AI/ML Engineer
- **Actions:**
  - Implemented explainable, deterministic rule-based household risk scoring (0-100) in `risk.py`:
    - Senior Citizen 60+: +25 (75+: +30)
    - Living alone: +20
    - Tin / Asbestos roof: +15
    - Outdoor worker: +10
    - Pre-existing medical vulnerability: +15
    - Unchecked today on Orange/Red day: +20
    - Active unresolved SOS: +25
    - Capped at 100 with clear explainable reason strings.
  - Added climate-zone-aware 3-day predictive heat outlook analyzing temperature trends (Hotter/Cooler/Stable) and Red day forecast.
  - Created and ran `tests/check_risk_weights.py` verifying that elderly residents in poor housing (e.g. Ram Prasad, age 78, tin roof, score 100) rank significantly higher than younger individuals in concrete houses (Mukesh Yadav, score 45).

---

## Role 5: Frontend Engineer
- **Actions:**
  - Authored clean Jinja2 templates matching `docs/DESIGN.md` tokens.
  - Implemented `static/css/style.css` without external UI frameworks.
  - Implemented `static/js/main.js` with client-side double-submission prevention (`prevent-double-submit` class) and HTML5 geolocation.
  - Integrated Leaflet.js with circle markers colored by vulnerability and rectangular cooling shelter markers.
  - Integrated Chart.js bar graphs for 7-day municipal check-in trends.
  - Connected bilingual translations dictionary in `translations.py` and large-text accessibility mode.
  - Implemented dynamic AJAX cascade in `templates/register.html` for State > City > Ward selection.

---

## Role 6: QA Engineer
- **Actions:**
  - Built comprehensive `unittest` test suite covering:
    - Mathematical heat index and climate zone thresholds (`tests/test_risk.py`).
    - Auto-assignment caps, ward matching, and distance tie-breaking (`tests/test_assignment.py`).
    - State > City > Ward location helpers and cross-city data isolation (`tests/test_locations.py`).
    - End-to-end smoke workflows and the 5-step hackathon demo sequence (`tests/test_smoke.py`).
  - Executed automated test suite (18/18 tests passing).
  - Verified zero open bugs in `docs/BUGS.md`.
