# Research & Scientific Grounding for HeatShield

This document details the scientific foundations, meteorological standards, vulnerability factors, Open-Meteo API specifications, coordinate verifications, emergency services applicability, and operational assumptions used throughout HeatShield.

---

## 1. Heat Index Calculation (Rothfusz Regression)

### 1.1 Mathematical Formula
The National Weather Service (NWS) calculates apparent temperature using the polynomial regression developed by Lans P. Rothfusz (1990, NWS Technical Attachment SR 90-23), grounded in Steadman's biometeorological model of human thermoregulation.

For temperature $T$ in degrees Fahrenheit ($^\circ\text{F}$) and relative humidity $RH$ as a percentage ($0-100$):

First, a simplified Steadman equation is tested:
$$HI_{\text{simple}} = 0.5 \times (T + 61.0 + [(T - 68.0) \times 1.2] + [RH \times 0.094])$$

If $(HI_{\text{simple}} + T) / 2 \ge 80^\circ\text{F}$, the full 9-term Rothfusz regression is computed:
$$HI = -42.379 + 2.04901523\,T + 10.14333127\,RH - 0.22475541\,T\,RH - 0.00683783\,T^2 - 0.05481717\,RH^2 + 0.00122874\,T^2\,RH + 0.00085282\,T\,RH^2 - 0.00000199\,T^2\,RH^2$$

### 1.2 Edge Adjustments & Validity
- **Low Humidity Adjustment:** If $RH < 13\%$ and $80^\circ\text{F} \le T \le 112^\circ\text{F}$:
  $$\text{Adj}_{\text{low}} = \frac{13 - RH}{4} \times \sqrt{\frac{17 - |T - 95|}{17}}$$
  $$HI = HI - \text{Adj}_{\text{low}}$$
- **High Humidity Adjustment:** If $RH > 85\%$ and $80^\circ\text{F} \le T \le 87^\circ\text{F}$:
  $$\text{Adj}_{\text{high}} = \frac{RH - 85}{10} \times \frac{87 - T}{5}$$
  $$HI = HI + \text{Adj}_{\text{high}}$$

**Conversion to Celsius:**
$$T_{\text{C}} = (T_{\text{F}} - 32) \times \frac{5}{9}$$

**Valid Range and Constraints:**
- The full Rothfusz regression is valid when $T \ge 80^\circ\text{F}$ ($\approx 26.7^\circ\text{C}$) and $RH \ge 40\%$. Below $80^\circ\text{F}$, apparent temperature is roughly equal to dry-bulb temperature (or Steadman simple).
- **Physical Assumptions:** Assumes light clothing, shaded environment, and a light 5-knot ($2.6\text{ m/s}$) breeze. Exposure to direct radiant sunlight adds an estimated $8^\circ\text{C}$ ($15^\circ\text{F}$) to effective biological heat stress.

**Sources:**
- NOAA / National Weather Service Heat Index Equation: [weather.gov/safety/heat-index](https://www.weather.gov/safety/heat-index)
- Rothfusz, L. P. (1990). *The Computation and Use of the Heat Index in Meteorological Operations*. NWS Technical Attachment SR 90-23.
- Steadman, R. G. (1979). *The Assessment of Sultriness. Part I: A Temperature-Humidity Index Based on Human Physiology and Clothing Science*. Journal of Applied Meteorology, 18(7), 861-873.

---

## 2. IMD Heatwave Criteria vs. HeatShield Day Levels Across Climate Zones

### 2.1 India Meteorological Department (IMD) Official Criteria
IMD declares heatwaves based on geographical climate zones and maximum daily temperatures:
1. **Plains Region:**
   - Baseline threshold: Maximum temperature reaches at least $40.0^\circ\text{C}$.
   - *Heat Wave:* Departure from normal is $+4.5^\circ\text{C}$ to $+6.4^\circ\text{C}$, or actual maximum temperature $\ge 45.0^\circ\text{C}$.
   - *Severe Heat Wave:* Departure $> +6.4^\circ\text{C}$, or actual maximum temperature $\ge 47.0^\circ\text{C}$.
2. **Coastal Region:**
   - Baseline threshold: Maximum temperature reaches at least $37.0^\circ\text{C}$.
   - *Heat Wave:* Departure from normal $\ge +4.5^\circ\text{C}$, or actual maximum temperature $\ge 37.0^\circ\text{C}$.
3. **Hilly / Mountainous Region:**
   - Baseline threshold: Maximum temperature reaches at least $30.0^\circ\text{C}$.
   - *Heat Wave:* Departure from normal $\ge +4.5^\circ\text{C}$, or actual maximum temperature $\ge 30.0^\circ\text{C}$.

**Sources:**
- India Meteorological Department (IMD): *Criteria for Declaring Heat Wave in India*, National Weather Forecasting Centre, New Delhi. [mausam.imd.gov.in](https://mausam.imd.gov.in)
- National Disaster Management Authority (NDMA): *National Guidelines for Preparation of Action Plan - Prevention and Management of Heat Wave* (Government of India).

---

### 2.2 HeatShield Operational Thresholds per Climate Zone
Because HeatShield monitors Apparent Temperature (Heat Index, combining dry-bulb temperature and humidity) to capture real biological thermoregulatory distress, thresholds are calibrated per climate zone:

| Climate Zone | Green (Normal) | Orange (Alert / High Risk) | Red (Emergency / Severe) | Justification & Grounding |
|--------------|----------------|----------------------------|--------------------------|---------------------------|
| **Plains**   | $< 35^\circ\text{C}$ | $35^\circ\text{C}$ to $41^\circ\text{C}$ | $> 41^\circ\text{C}$ | Standard IMD plain heatwave correlation with US NOAA Extreme Caution / Danger bands. |
| **Coastal**  | $< 33^\circ\text{C}$ | $33^\circ\text{C}$ to $38^\circ\text{C}$ | $> 38^\circ\text{C}$ | High ambient relative humidity ($>70\%$) impairs evaporative sweating. Aligns with IMD $37^\circ\text{C}$ coastal threshold adapted for humidity. |
| **Hill**     | $< 26^\circ\text{C}$ | $26^\circ\text{C}$ to $30^\circ\text{C}$ | $> 30^\circ\text{C}$ | Mountain architecture traps heat (glass, insulation), steep topography raises physical exertion, and unacclimatized populations experience heat exhaustion at lower absolute temperatures. Aligns with IMD $30^\circ\text{C}$ hill trigger. |

*Note on Calibration:* The adaptation from IMD dry-bulb to Heat Index threshold is a verified **prototype operational assumption** to enable universal triage using apparent temperature.

---

## 3. Human Heat-Vulnerability Risk Factors

The scientific rationale for household scoring weights is derived from epidemiological studies of urban heat islands in South Asia:

1. **Age $\ge 60$ (+25 points) and $\ge 75$ (+30 points):**
   - *Evidence:* Reduced thermoregulatory peripheral vasodilation, slower sweat onset, blunted thirst response, and higher cardiovascular strain (WHO & National Institute of Disaster Management - NIDM Heat Action Plans).
2. **Living Alone (+20 points):**
   - *Evidence:* Absence of early cognitive confusion detection by family members. Mortality spikes among socially isolated seniors during heatwaves (Ahmedabad Heat Action Plan findings, NRDC).
3. **Tin / Asbestos Roof (+15 points):**
   - *Evidence:* Corrugated galvanized iron (tin) and asbestos sheeting exhibit high thermal conductivity and low thermal mass. Indoor daytime temperatures often exceed outdoor ambient temperatures by $3^\circ\text{C}$ to $6^\circ\text{C}$ with severe night-time heat trapping (Mahila Housing Trust / NRDC Ahmedabad studies).
4. **Outdoor Workers (+10 points):**
   - *Evidence:* E.g., cycle-rickshaw pullers, street vegetable vendors, construction labourers. Metabolic heat production coupled with high solar irradiance and lack of workplace cooling leads to rapid dehydration and heat exhaustion (International Labour Organization guidelines).
5. **Pre-existing Medical Needs (+15 points):**
   - *Evidence:* Hypertension, diabetes, renal disease, and diuretic medication use diminish physiological capacity to handle fluid deficits (Lancet Countdown on Health and Climate Change).
6. **No Check-in Today on Orange/Red Days (+20 points):**
   - *Operational Trigger:* Signals potential acute incapacitation, delirium, or loss of consciousness.
7. **Open Unresolved SOS (+25 points):**
   - *Critical Trigger:* Active distress beacon requiring immediate prioritization.

---

## 4. Open-Meteo API Specification

- **Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Method:** `GET` with HTTP query parameters:
  - `latitude`: Float (e.g. `28.3670`)
  - `longitude`: Float (e.g. `79.4304`)
  - `current`: `temperature_2m,relative_humidity_2m,apparent_temperature,weather_code`
  - `daily`: `temperature_2m_max,apparent_temperature_max,precipitation_probability_max`
  - `timezone`: `Asia/Kolkata`
- **Units:**
  - `temperature_2m`: Degrees Celsius ($^\circ\text{C}$)
  - `relative_humidity_2m`: Percentage ($\%$)
  - `apparent_temperature`: Degrees Celsius ($^\circ\text{C}$)
- **Reliability:** Timeout is set to 5.0 seconds. A deterministic simulated weather fallback runs when network connectivity or API quotas fail. Cache TTL is configured to 30 minutes in `config.py`.

---

## 5. Seed Geographic Coordinates and Climate Zones

All seed coordinates have been cross-checked against municipal boundary maps and survey coordinates:

### Demo Cities (Across 4 Distinct Geographical Regions and 3 Climate Zones)
1. **Bareilly (Uttar Pradesh)** - *Zone: Plains*
   - City Center: `28.3667` N, `79.4317` E
   - Wards:
     - Civil Lines: `28.3670`, `79.4304`
     - Quila: `28.3620`, `79.4120`
     - Subhash Nagar: `28.3490`, `79.4080`
     - C.B. Ganj: `28.3950`, `79.3620`
     - Old City: `28.3540`, `79.4240`
     - Izzatnagar: `28.3980`, `79.4350`
2. **Jaipur (Rajasthan)** - *Zone: Plains*
   - City Center: `26.9124` N, `75.7873` E
   - Wards:
     - C-Scheme: `26.9100`, `75.7980`
     - Johari Bazar: `26.9200`, `75.8240`
     - Mansarovar: `26.8550`, `75.7650`
     - Malviya Nagar: `26.8520`, `75.8150`
3. **Chennai (Tamil Nadu)** - *Zone: Coastal*
   - City Center: `13.0827` N, `80.2707` E
   - Wards:
     - T. Nagar: `13.0418`, `80.2341`
     - Mylapore: `13.0368`, `80.2676`
     - Royapuram: `13.1137`, `80.2954`
     - Adyar: `13.0012`, `80.2565`
4. **Kolkata (West Bengal)** - *Zone: Coastal*
   - City Center: `22.5726` N, `88.3639` E
   - Wards:
     - Park Street: `22.5510`, `88.3520`
     - Shyambazar: `22.6020`, `88.3710`
     - Gariahat: `22.5190`, `88.3680`
     - Howrah Station Area: `22.5850`, `88.3420`
5. **Shimla (Himachal Pradesh)** - *Zone: Hill*
   - City Center: `31.1048` N, `77.1734` E
   - Wards:
     - Mall Road: `31.1045`, `77.1740`
     - Sanjauli: `31.1010`, `77.1950`
     - Chotta Shimla: `31.0920`, `77.1810`
     - Boileauganj: `31.1050`, `77.1420`

All seeded household and cooling point coordinates strictly reside within their respective ward boundaries.

---

## 6. Emergency Medical Dispatch and Hotlines

1. **National Emergency Helpline `112`:**
   - Implemented under the Emergency Response Support System (ERSS) nationwide by the Ministry of Home Affairs (MHA), Government of India.
   - Replaces or integrates 100 (Police), 101 (Fire), and 108 (Health) into a single pan-India dispatch number.
   - Primary hotline displayed on all emergency interfaces across HeatShield.
2. **`108` Emergency Medical Ambulance Service:**
   - Active across Uttar Pradesh, Rajasthan, Tamil Nadu, Himachal Pradesh, Gujarat, Karnataka, Andhra Pradesh, and Telangana under the National Health Mission (NHM) public-private partnership.
   - Applicable to our seeded demo locations (UP, Rajasthan, Tamil Nadu, Himachal Pradesh).

---

## 7. Assumptions and Known Limits

1. **Prototype Assumption:** Weather is sampled at the city reference coordinates for each ward. Micro-climatic urban heat island (UHI) temperature differences between wards are modeled through the building roof type factor rather than ward-by-ward micro sensors.
2. **Threshold Adaptation:** IMD heatwave definitions use dry-bulb air temperature with departures from climatological normal. HeatShield utilizes Apparent Temperature (Heat Index) calibrated to equivalent physiological danger zones for each climate zone.
3. **Emergency Disclaimers:** HeatShield is a community triage and volunteer coordination platform; it is not an emergency response dispatch service. In critical life-threatening situations, users are guided to dial 112 or 108 immediately.
