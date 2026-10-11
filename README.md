# HeatShield — Pan-India Municipal Heatwave Response Network

> **LIVE URL:** [https://heatshield.ap-south-1.awsapprunner.com](https://heatshield.ap-south-1.awsapprunner.com) *(AWS App Runner in `ap-south-1` &mdash; see [DEPLOY.md](DEPLOY.md) for deployment guide)*

HeatShield is an open-source, multi-tenant heatwave response platform designed for municipal corporations, disaster management authorities, humanitarian field volunteers, and vulnerable residents across India. During extreme summer heatwaves, elderly individuals living alone, outdoor labourers (cycle-rickshaw pullers, construction workers, street vendors), and families in tin-roof or asbestos-roof housing face severe, life-threatening heat illness without anyone knowing their daily condition. 

HeatShield determines daily heat danger using localized Apparent Temperature (Heat Index) calibrated across India's three major climate zones (Plains, Coastal, Hill), calculates an explainable, rule-based vulnerability triage score (0–100) for every household, runs automated volunteer visit auto-assignment, and coordinates emergency hydration and cooling shelter response in real time.

---

## 1. Built for All of India

HeatShield is designed from the ground up for pan-India deployment with zero hardcoded municipal assumptions:
- **State > City > Ward Geographic Hierarchy:** Locations are strictly structured in the `locations` table. The application ships with `data/india_cities.json` containing 42 major cities across more than 20 Indian States and Union Territories.
- **Three Verified Climate Zones:**
  1. **Plains:** Gangetic and peninsular plains (e.g. Bareilly, Jaipur, Lucknow, Delhi, Bhopal, Nagpur). Baseline IMD heatwave threshold 40°C; HeatShield Apparent Temperature thresholds: Green $<35^\circ\text{C}$, Orange $35-41^\circ\text{C}$, Red $>41^\circ\text{C}$.
  2. **Coastal:** High relative humidity impairs evaporative cooling (e.g. Chennai, Kolkata, Mumbai, Kochi, Visakhapatnam). HeatShield Apparent Temperature thresholds: Green $<33^\circ\text{C}$, Orange $33-38^\circ\text{C}$, Red $>38^\circ\text{C}$.
  3. **Hill / Mountainous:** High altitude, unacclimatized population, and cold-insulated housing (e.g. Shimla, Dharamshala, Dehradun, Nainital, Srinagar, Shillong). IMD hill heatwave threshold 30°C; HeatShield thresholds: Green $<26^\circ\text{C}$, Orange $26-30^\circ\text{C}$, Red $>30^\circ\text{C}$.
- **Strict Multi-City Tenant Isolation:** Ward admins and volunteers are strictly scoped by their `city_id`. A ward admin or volunteer in Bareilly can never view, assign, or alter households, alerts, volunteers, or cooling centers in Jaipur or Chennai.
- **Adding a New City or Ward:**
  - *Via UI:* A Super Admin can log in (`/admin/super`) and add any new Indian State, City, Climate Zone, and Municipal Ward directly through the web form.
  - *Via JSON:* Add the city object to `data/india_cities.json` (name, state, latitude, longitude, climate_zone) and it is automatically ingested into the database on startup.
- **Language Verification:**
  - **English (`en`):** 100% human-reviewed and verified.
  - **Hindi (`hi`):** 100% human-reviewed and verified for all public alerts, navigation, volunteer field cards, and resident check-in controls.
  - *Structure:* Centralized in [translations.py](file:///c:/Users/LOQ/OneDrive/Desktop/TRAINLY/heatshield/translations.py) as a dictionary block, allowing state languages (Tamil, Bengali, Marathi, Telugu) to be added as a single contiguous block.
- **Emergency Helplines:** Prominently displays the unified National Emergency Support System number **112** on all emergency sections. Displays **108** for emergency medical ambulance assistance in verified participating states.

---

## 2. Evidence and Assumptions

Scientific foundations and empirical meteorological rules are documented in detail in [docs/RESEARCH.md](file:///c:/Users/LOQ/OneDrive/Desktop/TRAINLY/heatshield/docs/RESEARCH.md).
- **Rothfusz Apparent Heat Index:** Calculates physiological thermoregulatory strain from dry-bulb air temperature and relative humidity using the 9-term polynomial equation with boundary humidity adjustments (NOAA / NWS SR 90-23).
- **IMD Criteria Grounding:** Day threat levels are mapped to physiological impact zones adapted from India Meteorological Department (IMD) criteria for plains, coastal, and hill zones.
- **Epidemiological Risk Weights:** Scoring rules (0–100) are derived from South Asian urban heat island studies (WHO, Ahmedabad Heat Action Plan, NRDC, Lancet Countdown):
  - Age 60+ (+25 points) or 75+ (+30 points)
  - Living alone (+20 points)
  - Tin or asbestos roof (+15 points)
  - Outdoor physical worker (+10 points)
  - Chronic medical condition entered (+15 points)
  - Missing check-in by 12:00 PM on Orange/Red days (+20 points)
  - Active unresolved SOS beacon (+25 points)
  - Total score is capped at 100 with clear human-readable explanations.

---

## 3. What is Rule-Based vs. What Uses AI

- **Rule-Based (100% Deterministic & Explainable):**
  - **Household Vulnerability Scoring:** Uses transparent, deterministic clinical rules so municipal officers can immediately see *why* an elderly resident was prioritized (e.g. "Age 78, Lives alone, Tin roof, No check-in today").
  - **Volunteer Auto-Assignment:** Deterministic capacity-constrained matching (nearest volunteer in the same ward, capped at 8 households per volunteer per day).
  - **12:00 PM Cutoff Rule:** Rule-based promotion of unchecked high-risk households (score $\ge 60$) to the top of volunteer queues.
  - **3-Day Predictive Heat Outlook:** Algorithmic calculation based on 72-hour forecast temperature deltas ($\Delta T \ge 1.5^\circ\text{C}$ = Hotter, $\le -1.5^\circ\text{C}$ = Cooler, otherwise Stable) and projected Red-alert count.
- **AI / LLM Integration (Status: Future Scope):**
  - Generative AI (such as Amazon Bedrock) for conversational safety guidance in local dialects was evaluated. In this student prototype, safety advice is hardcoded in [translations.py](file:///c:/Users/LOQ/OneDrive/Desktop/TRAINLY/heatshield/translations.py) to guarantee instant offline response times, eliminate hallucination risks, and protect resident PII from third-party APIs.

---

## 4. Key Features

- **Public Landing Page:** Explains the core problem in 3 plain sentences and the solution in 3 actionable steps. No generic startup gradient hero.
- **Resident Portal:**
  - Real-time heat level indicator (Green / Orange / Red) with clear health advisories for the resident's city.
  - One-tap "I'm okay" check-in button with double-submission lockout.
  - Immediate emergency SOS beacon with 112 emergency advice.
  - Vulnerability profile editor with HTML5 GPS coordinate capture and manual fallback.
  - Leaflet map of municipal cooling shelters, water kiosks, and emergency cold clinics scoped to the resident's city.
- **Volunteer Portal:**
  - Sunlight-readable mobile cards with large touch targets ($\ge 44\text{px}$).
  - Triage-sorted queue: missed 12:00 PM check-ins at top, followed by highest risk score and shortest walking distance (Haversine formula).
  - Rapid visit logging: Checked (Safe), Needs Help, or Not Reachable, plus relief supplies given (ORS packets, water bottles, umbrellas).
  - Activity log with earned badges (e.g., "First Responder", "Hydration Hero").
- **Ward Admin Operations Room:**
  - Executive KPI cards: Total households, checked today, unchecked high-risk, active SOS alarms, active volunteers.
  - Interactive Leaflet heat map displaying household risk levels and cooling shelters in the city.
  - 7-day daily check-in bar chart powered by Chart.js.
  - 3-day predictive heat outlook.
  - One-click auto-assignment algorithm matching households to nearest ward volunteers.
  - Demo simulation toolbar: Force Green/Orange/Red weather and simulate 12:00 PM check-in cutoff.
  - Broadcast emergency SMS alerts via Amazon Simple Notification Service (SNS).
  - Cooling center capacity and occupancy tracking.
  - Weekly report summary with downloadable CSV audit logs.
- **Super Admin Pan-India Overview:**
  - Nationwide surveillance table sorting all cities by alert level, households, unchecked high-risk cases, and open SOS beacons.
  - Pan-India Leaflet map with colored threat markers across all registered Indian cities.
  - Global demo weather override switch.
  - Interactive form to add new cities, climate zones, and municipal wards.

---

## 5. Technology Stack (Strict)

- **Backend:** Python 3.11+ with Flask
- **Database:** SQLite with built-in `sqlite3` module (strict foreign keys, parameterized queries, no ORM).
- **Frontend:** Jinja2 templates, plain CSS (`static/css/style.css`), vanilla JavaScript (`static/js/main.js`).
- **Maps:** Leaflet.js + OpenStreetMap (CDN, no API key required).
- **Charts:** Chart.js (CDN).
- **AWS:** `boto3` for Amazon SNS with simulated fallback.
- **Allowed Dependencies:** `flask`, `requests`, `boto3`, `gunicorn`.

---

## 6. How to Run on Windows

1. Open PowerShell or Command Prompt in the project folder:
   ```powershell
   cd c:\Users\LOQ\OneDrive\Desktop\TRAINLY\heatshield
   ```
2. Create and activate a Python virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Start the application:
   ```powershell
   python app.py
   ```
5. Open your browser at:
   ```
   http://127.0.0.1:5000
   ```
*Note:* The database creates itself and seeds demo data automatically on the first run.

---

## 7. Seeded Demo Accounts

| Role | Username | Password | Purpose & Scope |
|---|---|---|---|
| **Super Admin** | `superadmin` | `admin123` | Nationwide oversight: all-India map, multi-city table, add cities/wards, global demo switch |
| **Ward Admin (Bareilly)** | `admin` | `admin123` | Bareilly ward control room, heat map, broadcast alerts, demo mode override |
| **Ward Admin (Jaipur)** | `admin_jaipur` | `admin123` | Jaipur control room, desert heat triage, cooling centers |
| **Field Volunteer (Bareilly)** | `vol_amit` | `vol123` | Quila ward visits, prioritize missed check-ins, record ORS delivery |
| **Field Volunteer (Jaipur)** | `vol_vikram` | `vol123` | Johari Bazar ward visits, desert heat field triage |
| **High-Risk Resident** | `res_ram` | `res123` | Ram Prasad (Age 78, tin roof, lives alone, Bareilly) &mdash; Unchecked |
| **Resident 2 (Ready to Check-in)** | `res_shanti` | `res123` | Shanti Devi (Age 68, Bareilly) &mdash; Test the "I'm okay" button |

---

## 8. The 5-Step Demo Script (Judge Walkthrough)

Follow these exact 5 steps during a presentation to demonstrate the complete emergency triage cycle:

1. **Step 1: Admin Sets Red Alert**
   - Log in as `admin` (`admin123`).
   - In the Demo toolbar at the top of the dashboard, switch "Force Heat Level" to **Red**.
   - Notice the dashboard transitions to Red Alert, broadcast notifications go out (SNS or simulated), and visits are auto-assigned across volunteers.
2. **Step 2: Resident Check-In vs. Non-Check-In**
   - Open another browser window (or log out), log in as `res_shanti` (`res123`).
   - Tap the large green **"I'm okay today"** button. The button disables immediately and confirms her safety.
   - Resident `res_ram` (`res123`) does not check in.
3. **Step 3: Simulate 12:00 PM Cutoff**
   - Switch back to the admin dashboard (`admin`).
   - Click the **"Simulate 12:00 Cutoff"** button.
   - Log in as field volunteer `vol_amit` (`vol123`).
   - Notice that `res_ram` (Ram Prasad) has moved directly to the **very top of the visit list** with a red "MISSED 12:00 CHECK-IN" badge because his score exceeds 60 on a Red day.
4. **Step 4: Volunteer Visit & Relief Distribution**
   - In the volunteer portal (`vol_amit`), locate Ram Prasad's priority card.
   - Select supplies given: **ORS Packets**.
   - Enter note: *"Resident feeling dehydrated, resting in shade, administered ORS."*
   - Tap **"Needs Help"**.
5. **Step 5: Admin Resolves Case & Opens Shelter**
   - Return to the admin dashboard (`admin`).
   - Notice the open SOS/distress alerts banner immediately displays Ram Prasad flagged from the field visit.
   - Click **"Resolve Case"**, enter note *"Dispatched mobile medical van"*, and submit.
   - Navigate to **Cooling Centres** to open an emergency shelter, or **Reports** to download the CSV activity record.

---

## 9. Amazon Web Services (AWS) Architecture & Honesty Table

| AWS Service | Status | Implementation Details |
|---|---|---|
| **AWS App Runner** | **Used for real now** | Production hosting in `ap-south-1` (Mumbai). Configured via `apprunner.yaml` and `Procfile` (`gunicorn -w 1 -b 0.0.0.0:8080 app:app`), health-checked via `/health`, with automatic deployment on GitHub push. |
| **Amazon SNS (Simple Notification Service)** | **Used for real now** | Real-time broadcast advisories and emergency SOS notifications via topic `heatshield-alerts` with email & SMS endpoints. Safe fallback to local logs when credentials/topic are unconfigured. |
| **AWS Lambda** | **Included in code, optional to deploy** | Daily morning automated heat-check handler in `lambda/heat_check_lambda.py` using Python standard library `urllib` to trigger `/api/daily-heat-check` via `X-Heat-Token`. |
| **Amazon EventBridge** | **Included in code, optional to deploy** | Daily morning cron schedule (`cron(0 0 * * ? *)` = 05:30 AM IST) to trigger the heat-check Lambda before peak daylight hours. |
| **Amazon Cognito** | *Future scope* | Citizen identity verification and SMS OTP login. |
| **Amazon DynamoDB** | *Future scope* | Serverless multi-region NoSQL persistence for multi-city scaling. |
| **Amazon Location Service** | *Future scope* | Geofencing and real-time turn-by-turn routing for volunteers on foot. |

### AWS App Runner Deployment
Complete step-by-step console instructions, IAM instance role definitions, and cost-control commands are detailed in [DEPLOY.md](DEPLOY.md).

---

## 10. How the Code Works (File-by-File Guide)

- **`app.py`**: The Flask application factory. Initializes the database on first run, registers all blueprints, configures global Jinja template helpers for translations and city scoping, and defines friendly 404/500 error pages.
- **`config.py`**: Centralized configuration specifying session secrets, token keys, weather cache durations, AWS SNS settings, and scientifically calibrated heat thresholds for plains, coastal, and hill zones.
- **`database.py`**: SQLite database manager utilizing Python's built-in `sqlite3` module. Enforces foreign key constraints, table schemas, per-city settings, and seeds demo data for Super Admin, Bareilly, Jaipur, Chennai, Kolkata, and Shimla.
- **`locations.py`**: Geographic management module that reads `data/india_cities.json` and manages State > City > Ward relationships and dynamic ward additions.
- **`risk.py`**: Mathematical and biometeorological core. Computes the official 9-term Rothfusz heat index with Steadman adjustments, assigns day threat levels by climate zone, calculates explainable 0–100 household risk scores, and generates the 3-day predictive heat outlook.
- **`distance.py`**: Great-circle distance helper using the spherical Haversine formula to calculate walking distance in kilometers between volunteers and households.
- **`weather.py`**: Weather data integration fetching Open-Meteo forecasts with a 5-second timeout, in-memory 30-minute caching, and a deterministic climate-zone-aware fallback.
- **`aws_services.py`**: Cloud messaging utility using `boto3` to publish SMS heat alerts and SOS notifications via Amazon SNS, with safe fallbacks when unconfigured.
- **`translations.py`**: Central bilingual dictionary containing human-reviewed English and Hindi translations for all UI labels, emergency advisories, and buttons.
- **`routes/auth.py`**: Handles user authentication, session creation, 10-digit Indian mobile validation (+91), role routing, and registration with dynamic State > City > Ward selection.
- **`routes/resident.py`**: Powers the resident experience: daily "I'm okay" check-in, SOS emergency triggering, vulnerability profile updates, and local cooling shelter directories.
- **`routes/volunteer.py`**: Serves mobile-optimized visit cards sorted by vulnerability and distance, and handles visit logging with relief supply tracking.
- **`routes/admin.py`**: Municipal command center managing auto-assignment algorithms, volunteer reassignments, demo weather overrides, 12:00 PM cutoff simulations, SOS resolution, and Super Admin pan-India surveillance.
- **`routes/api.py`**: REST API endpoints for dynamic location cascades and the token-secured `POST /api/daily-heat-check` morning automated workflow.
- **`lambda/heat_check_lambda.py`**: Lightweight AWS Lambda handler using standard library `urllib` to trigger daily heat checks via EventBridge.
- **`static/css/style.css`**: Pure CSS design system implementing governmental humanitarian styling tokens: warm paper `#FAF7F2`, high-contrast text `#1F1D1A`, terracotta accent `#C2410C`, and status chips without external frameworks.
- **`static/js/main.js`**: Client-side JavaScript handling double-submission lockout on emergency forms and HTML5 browser GPS coordinate retrieval.

---

## 11. Manual Testing Checklist

| Step | Action | Expected Result | Pass? |
|---|---|---|---|
| 1 | Visit `http://127.0.0.1:5000` | Landing page loads with 3-sentence problem, 3-step solution, and demo accounts | &#10003; |
| 2 | Click "Large Text [T+]" in header | Font size scales smoothly for elder readability | &#10003; |
| 3 | Click "हिन्दी में देखें" in header | All navigational elements, titles, and buttons switch to verified Hindi | &#10003; |
| 4 | Log in as `res_ram` and navigate to `/admin/dashboard` | Redirects to resident dashboard with "Access denied" flash alert | &#10003; |
| 5 | As `res_shanti`, tap "I'm okay today" | Button disables, shows "Recording...", and confirms safe check-in | &#10003; |
| 6 | In admin dashboard, switch Demo to "Red" | Heat level updates to Red, alert dispatches, and auto-assign triggers | &#10003; |
| 7 | In admin dashboard, tap "Simulate 12:00 Cutoff" | Volunteer `vol_amit` sees unchecked senior Ram Prasad at top of queue | &#10003; |
| 8 | As `vol_amit`, record visit with "Needs Help" | Flash success shows, and SOS alert appears in admin SOS log | &#10003; |
| 9 | In admin dashboard, resolve SOS alert | SOS status marks Resolved and response time in minutes is logged | &#10003; |
| 10 | Download CSV in Reports tab | Valid CSV file downloads with complete visit audit trail | &#10003; |
| 11 | Log in as `superadmin` | Pan-India overview page loads with all-India map and surveillance grid | &#10003; |
