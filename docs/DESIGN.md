# HeatShield Design Specification & Wireframes

This design specification is created for real-world municipal staff, field volunteers under direct sunlight, vulnerable elderly residents, and state disaster authorities across India.

---

## 1. Design System & Principles

### 1.1 Non-Negotiable Styling Rules
- **No generic startup aesthetics:** No purple/blue gradients, no neon glows, no glassmorphism, no floating abstract blobs, no emoji in headings, no gradient hero.
- **Aesthetic Identity:** Crisp governmental public-health bulletin meets humanitarian emergency field tool.
- **Background:** Warm archival paper `#FAF7F2` (`--bg-paper`)
- **Card Background:** Pure white `#FFFFFF` (`--bg-card`) with subtle border `#E5E0D8`
- **Text:** Carbon black `#1F1D1A` (`--text-main`), muted charcoal `#5A554E` (`--text-muted`)
- **Brand Accent:** Burnt terracotta orange `#C2410C` (`--accent`)
- **Status Semantic Palette:**
  - *Green / Safe:* `#2F7D4F` (`--status-green`, bg tint `#EAF5EE`)
  - *Amber / Orange / Caution:* `#D98A00` or `#C2410C` (`--status-orange`, bg tint `#FEF3C7`)
  - *Red / Emergency / Danger:* `#B42318` (`--status-red`, bg tint `#FEE4E2`)
- **Typography:**
  - Headings: `Source Serif 4`, Georgia, serif
  - Body / UI / Controls: `Inter`, system-ui, -apple-system, sans-serif
- **Scale:**
  - Heading 1: 1.875rem (30px), bold, tight tracking
  - Heading 2: 1.375rem (22px), semi-bold
  - Heading 3: 1.125rem (18px), medium
  - Body: 1rem (16px), line-height 1.5
  - Large-Text Mode: Root scaling from 16px to 19px for elder accessibility (persisted in session).
- **Controls & Buttons:** Flat, 1px solid borders, border-radius 4px to 6px, minimum tap target 44px on mobile.

---

## 2. User Flows by Role

### 2.1 Public / Home Flow
```
[Home Page (/)]
 ├── 3 Plain Sentences explaining HeatShield's purpose
 ├── 3 Operational Steps (Assess, Prioritize, Protect)
 ├── Demo Account quick switcher / credentials box
 └── [Login] / [Register]
```

### 2.2 Resident Flow
```
[Register: State -> City -> Ward] or [Login]
       │
       ▼
[Resident Dashboard (/resident/dashboard)]
 ├── Today's Heat Threat Level (Green / Orange / Red) with plain language explanation
 ├── Single Primary Action: Large "I'm okay" check-in button (disabled after check-in)
 ├── Last check-in confirmation timestamp
 ├── Critical Emergency Action: "SOS - Need Urgent Help" (Call 112 note)
 ├── Today's actionable heat safety tips
 └── Active municipal ward alerts
       │
       ├──► [Resident Profile (/resident/profile)]: Age, living alone, roof type, outdoor worker, medical needs, emergency contact (+91), GPS "Use my location" button
       ├──► [Cooling Points (/resident/cooling)]: Leaflet map + list of water kiosks, cooling shelters, hospitals
       └──► [Safety Guide (/safety-guide)]: Heatstroke signs, first aid, safe hours
```

### 2.3 Field Volunteer Flow (Sunlight & Mobile-Optimized)
```
[Volunteer Login]
       │
       ▼
[Today's Visits (/volunteer/visits)]
 ├── Top Priority Section: Missed 12:00 PM check-ins & Open SOS cases
 ├── Ordered Household Cards:
 │    - Highest Risk Score first
 │    - Distance tie-breaker (nearest first)
 │    - Key risk indicators chips ("Age 78", "Lives alone", "Tin roof")
 └── Quick Field Triage Actions (>= 44px buttons):
      ├── [ Checked - Safe ]
      ├── [ Needs Help ]
      └── [ Not Reachable ]
      └── Record supplies given (ORS, Water, Umbrella, None) + Field notes
       │
       └──► [My Activity (/volunteer/activity)]: Visit history, counts, badges ("First Responder", "Hydration Hero")
```

### 2.4 Municipal Ward Admin Flow (Desktop Operations)
```
[Admin Login]
       │
       ▼
[Admin Dashboard (/admin/dashboard)]
 ├── Metric Summary Cards: Total Households | Checked Today | Unchecked High-Risk | Open SOS | Active Volunteers
 ├── Ward Heat Map (Leaflet): Risk-colored household pins & cooling centers
 ├── Check-ins Trend (Chart.js 7-day bar chart)
 ├── 3-Day Heat Outlook (trend and red days forecast)
 ├── Demo Control Toolbar: Force Green / Orange / Red + "Simulate 12:00 Cutoff"
 └── Primary Action: [ Auto-Assign Field Volunteers ]
       │
       ├──► [Households (/admin/households)]: Filter by risk & ward, search, manual volunteer dropdown assignment
       ├──► [SOS Incident Tracker (/admin/sos)]: Open SOS alerts, response time calculator, resolve with notes
       ├──► [Cooling Points (/admin/cooling)]: Add/edit shelters, water kiosks, hospitals, open/closed toggle, occupancy
       ├──► [Ward Alerts (/admin/alerts)]: Broadcast message, pick ward or city-wide, SNS integration
       └──► [Reports (/admin/reports)]: Weekly summary metrics + Download CSV
```

### 2.5 Super Admin Flow (All-India Multi-City Oversight)
```
[Super Admin Login]
       │
       ▼
[Super Admin Overview (/admin/super)]
 ├── India Map (Leaflet): Major cities colored by heat level (Green / Orange / Red)
 ├── All-Cities Operational Grid: Sortable table (Level, Households, Unchecked High-Risk, Open SOS, Volunteers)
 ├── Global Demo Override Switch
 └── Municipal Administration: Add new state / city / ward with climate zone
```

---

## 3. Text Wireframes

### 3.1 Resident Dashboard (Mobile First)
```
+-----------------------------------------------------------------+
| [Sun & Shield Logo] HeatShield  | EN / हिन्दी | Large Text [T]   |
+-----------------------------------------------------------------+
| [BROADCAST ALERT IF ACTIVE]                                     |
| Severe Heat Warning: Civil Lines - Stay indoors 12:00 - 4:00 PM |
+-----------------------------------------------------------------+
| TODAY'S HEAT LEVEL: RED (EMERGENCY)                             |
| Current apparent temperature in your city: 42.1°C               |
| Dangerous heat conditions. Stay indoors and drink fluids.       |
+-----------------------------------------------------------------+
|                                                                 |
|   +---------------------------------------------------------+   |
|   |                 [   I'M OKAY TODAY   ]                  |   |
|   |         (Tap once to let the ward know you are safe)    |   |
|   +---------------------------------------------------------+   |
|   Last checked in: Today at 09:15 AM (Safe)                     |
|                                                                 |
|   +---------------------------------------------------------+   |
|   |         [ ! SOS - NEED IMMEDIATE ASSISTANCE ! ]         |   |
|   |       In life-threatening medical emergency call 112    |   |
|   +---------------------------------------------------------+   |
|                                                                 |
+-----------------------------------------------------------------+
| TODAY'S ADVICE: Drink ORS or lemon water every hour. Keep cool. |
| [Cooling Centers Map]  |  [Update Health Profile]  |  [Guide]   |
+-----------------------------------------------------------------+
| Prototype with demo data. Not for real emergencies. Call 112.   |
+-----------------------------------------------------------------+
```

### 3.2 Volunteer Field Card (High Sunlight Contrast)
```
+-----------------------------------------------------------------+
| RAM PRASAD (Age 78)                     SCORE: 95 [CRITICAL]   |
| Address: House 14, Gali 3, Quila Ward   Distance: 0.4 km away   |
| Phone: +91 98765 43210                  Status: MISSED CHECK-IN |
+-----------------------------------------------------------------+
| Vulnerability: Age 75+ (+30), Lives alone (+20), Tin roof (+15), |
| Chronic hypertension (+15), Missed check-in today (+20)        |
+-----------------------------------------------------------------+
| [ Checked - Safe ]     [ Needs Help ]     [ Not Reachable ]     |
| Supplies: [ ORS Packet [v] ]   Notes: [ Resident resting in shade]|
| [ Submit Visit Report ]                                         |
+-----------------------------------------------------------------+
```

---

## 4. Design States & Interactions

1. **Status Chips & Badges:**
   - `.chip-green`: `#2F7D4F` text on `#EAF5EE` bg, 1px border `#A3D9B5`.
   - `.chip-orange`: `#C2410C` text on `#FEF3C7` bg, 1px border `#FCD34D`.
   - `.chip-red`: `#B42318` text on `#FEE4E2` bg, 1px border `#FECDCA`.
2. **Double-Submission Lockout:**
   - Forms submitting critical records (Check-in, SOS, Visit report, Broadcast) disable the submit button immediately upon click with text `Submitting...` or `Recording...`.
3. **Empty States:**
   - Every table and list includes human-readable fallback when count is 0:
     - No visits: "No visits assigned to you today. Enjoy the cool weather or stand by for ward assignments."
     - No SOS: "No active SOS alerts. All flagged residents have been attended to."
     - No cooling points: "No registered cooling stations in this ward yet. Ward admin can register new points."
4. **Accessible Form Inputs:**
   - High contrast `#1F1D1A` borders, explicit `<label>` elements with `for` attribute, helper text for 10-digit Indian mobile numbers (+91).
