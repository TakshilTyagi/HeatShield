# HeatShield UI Redesign Summary (Visual-Only)

## 1. Design Direction & Global System
- **Aesthetic**: Civic public-notice & municipal health service bulletin.
- **Palette**:
  - Paper Background: `#FAF7F2`
  - Text Primary: `#1F1D1A`
  - Text Muted: `#57524A`
  - Burnt Orange (Accent): `#C2410C`
  - Green (Normal / Safe): `#2F7D4F` (BG: `#EAF4EE`)
  - Amber (Alert / High Risk): `#D98A00` (BG: `#FEF7E6`)
  - Red (Emergency / Cutoff / SOS): `#B42318` (BG: `#FDF0ED`)
- **Typography**:
  - Body: `Inter`, system-ui, -apple-system, sans-serif
  - Headings: `Source Serif 4`, Georgia, serif
- **Component Geometry**:
  - Flat 1px borders (`#DDD6CA`)
  - 4–6px border radii throughout
  - No gradients, glassmorphism, neon glows, or decorative motion
  - Focus states: High-visibility 2px solid `#C2410C` outline with 2px offset (`:focus-visible`)
  - High visual density with consistent spacing scale (`0.25rem` to `2rem`)

---

## 2. Page-by-Page Modifications (In Scope)

### 1) Global Shell (`templates/base.html` & `static/css/style.css`)
- Replaced previous CSS with strict civic design system rules.
- Set global paper background `#FAF7F2` and primary ink color `#1F1D1A`.
- Added civic badge `Public Notice` beside the hand-drawn sun-and-shield SVG.
- Removed all decorative emojis from headings and navigation items.
- Configured accessible `:focus-visible` ring across all interactive controls.
- Retained full support for Elder-friendly large-text mode (`body.large-text-mode`) and phone-width responsive layouts.

### 2) Home Page (`templates/home.html`)
- **Text-First & Serif Headline**: Clean header card featuring hand-drawn sun-and-shield SVG with `Source Serif 4` headline: *"Community Heatwave Protection Network"*.
- **3 Plain Sentences**: Clearly framed "The Problem" in exactly three direct, unembellished sentences on elder vulnerability, indoor heat-trap housing, and passive alert failures.
- **3 Coordinated Steps**: Clean flat 1px-bordered cards detailing Step 1 (Triage & Risk Scoring), Step 2 (Single-Tap Check-ins & SOS), and Step 3 (Dispatched Field Visits).
- **All-India Generic Scoping**: Removed specific city names (Bareilly/Jaipur) from descriptions and credentials table headers, generalizing to "Ward Admin (Plains)", "Ward Admin (Desert)", "Field Volunteer A/B", and "High-Risk Resident".
- **Action Buttons**: Prominent flat Sign In and Register buttons (`min-height: 44px`).

### 3) Resident Dashboard (`templates/resident_dashboard.html`)
- **Full-Width Heat Banner**: Prominent banner styled by alert level with explicit text label and icon (`[!] RED ALERT (EXTREME HEATWAVE)`, `[▲] ORANGE ALERT (SEVERE HEAT)`, `[✓] GREEN (NORMAL CONDITIONS)`) &mdash; never relying on color alone. Displays a clear, plain sentence of actionable advice alongside ambient temperature, humidity, and heat index.
- **Ultra-Large "I'm okay" Button**: Sized to `min-height: 64px` with `1.35rem` bold text (`.btn-resident-okay`) for effortless single-tap confirmation by elderly residents on touchscreen devices.
- **Clearly Separate SOS Box**: Placed in an isolated, bordered container (`.resident-sos-box`) with distinct red theme and prominent **112 / 108** medical emergency note.
- **Ward Advisories & Tips**: Crisp advisory cards for municipal notices and clean bulleted safety guidance.

### 4) Volunteer Visits Queue (`templates/volunteer_visits.html`)
- **Mobile-First Cards**: Preserved priority sorting while adding thick 6px left borders color-coded by vulnerability status (Red for &ge;70/SOS/missed cutoff, Amber for 45–69, Green for &lt;45).
- **Big Score Display**: Large `2rem` serif score counter (`score/100`) paired with category chip.
- **One-Line Reasons**: Formatted vulnerability reasons into a concise, high-contrast block (`reasons-line`).
- **Three Full-Width 56px Buttons**:
  - `Checked (Safe & Hydrated)` &mdash; Green, `min-height: 56px`, full width.
  - `Needs Immediate Assistance / Supplies` &mdash; Red, `min-height: 56px`, full width.
  - `Door Locked / Not Reachable` &mdash; Neutral, `min-height: 56px`, full width.
  Designed specifically for high legibility and easy tapping on phones in direct outdoor sunlight.

### 5) Ward Admin Dashboard (`templates/admin_dashboard.html`)
- **Operational Toolbar**: Flat, high-contrast demo control strip for weather overrides, 12:00 cutoff simulation, and auto-assignment.
- **Stat Cards Row**: 4 dense metric counters (Total Households, Checked Today, Unchecked High-Risk, Active SOS).
- **Side-by-Side Map & Chart**: Configured responsive CSS grid (`.admin-visuals-grid`) displaying the Leaflet risk map and Chart.js 7-day trend side-by-side on desktop, seamlessly stacking on mobile devices.
- **Dense Triage Table with Status Chips**: Added a comprehensive municipal household triage table directly below the map and chart, complete with status chips for risk category, daily welfare confirmation (`Checked Safe` / `Not Checked`), and SOS beacons.
