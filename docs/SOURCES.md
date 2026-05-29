# SOURCES.md — Research Behind Each Data Source

This document explains what we learned about each data source, how our sample data reflects that research, and what would break in a real deployment.

---

## Source 1: SAP Fuel & Procurement

### What we researched

SAP stores procurement and goods movement data primarily in two transaction families:
- **MB51** — Material Document List (goods movements, fuel consumption, stock transfers)
- **ME2M** — Purchase Orders by Material (purchase data with vendor, quantity, price)
- **Custom ABAP reports** — many enterprises have bespoke extracts that combine material master and accounting data

The export format from these transactions is a flat-file CSV. SAP's internal field names are German abbreviations from the original R/2 and R/3 system (pre-SAP S/4HANA):
- `BUKRS` = Buchungskreis (company code)
- `WERKS` = Werk (plant/site)
- `LIFNR` = Lieferantennummer (vendor number)
- `MATNR` = Materialnummer (material number)
- `MAKTX` = Materialbezeichnung (material description)
- `MENGE` = Menge (quantity)
- `MEINS` = Basismengeneinheit (base unit of measure)
- `NETPR` = Nettopreis (net price)
- `WAERS` = Währung (currency)
- `BLDAT` = Belegdatum (document date)
- `KOSTL` = Kostenstelle (cost centre)

SAP's date format in internal exports is `YYYYMMDD` (e.g. `20231215`). In German-locale systems it outputs `DD.MM.YYYY`. Some localised instances produce `DD/MM/YYYY`. All three appear in real exports from the same client.

SAP MEINS unit codes differ from ISO: `L` (litre), `KG` (kilogram), `M3` (cubic metre), `TO` (metric tonne), `KWH` (kilowatt-hour), `G` (gram), `GAL` (US gallon).

### What our sample data looks like and why

`sample_data/sap_fuel_procurement.csv` contains 20 rows designed to exercise every realistic scenario:

| Rows | Scenario |
|---|---|
| Most rows | Standard SAP field names (BUKRS, WERKS, etc.) |
| All rows | Three SAP date formats (YYYYMMDD as BLDAT) |
| Row 10 | Non-fuel procurement (stationery) — missing quantity/unit, mapped to PROCUREMENT |
| Row 12 | Anomalously high gas consumption (52,000 m³) — triggers suspicious flag |
| Row 19 | Blank document date + blank MBLNR — fails parsing |
| Row 20 | Unknown plant code `9999` — not in SiteMapping, flagged as suspicious |

Fuel categories are inferred from MAKTX (material description) by keyword matching — this is how a real SAP extract works when you don't have access to the material group classification (MARA-MTART).

### What would break in a real deployment

1. **Material classification**: We infer fuel type from the description text. A real deployment needs access to the SAP material master (MARA table) to get the material group, which is the reliable classification. Description-based guessing will mis-classify items.
2. **Multiple company codes**: Acme has one company code (GB01). A multinational client with 20 country company codes has 20 different BUKRS values, different currencies, and potentially different date formats per locale.
3. **Standard vs custom fields**: Many SAP instances have custom Z-fields appended to exports. Our parser ignores unknown columns, which is correct, but custom fields may contain data we need (e.g. a custom field for energy type).
4. **Encoding**: SAP exports can be CP1252 (Windows Latin-1), ISO-8859-1, or UTF-8 depending on the system locale. We use `utf-8-sig` with `errors=replace` which handles BOM and most Western European characters but will mangle CJK characters in Asian deployments.
5. **Line endings**: SAP on Windows outputs `\r\n`; on Unix `\n`. Python's csv module handles both, so this is low risk.

---

## Source 2: Utility Electricity

### What we researched

UK electricity suppliers (EDF, British Gas, Octopus Business, SSE, Npower/E.ON) all offer CSV downloads from their business portal. US utilities (PG&E, Con Edison, Ameren) similarly offer CSV via their business accounts.

Key realities we learned:
- **Billing periods do not align with calendar months.** A meter is read on whatever day the engineer visits or the smart meter reports. A January bill might run 17 Jan to 16 Feb. This is why we store `period_start` and `period_end` separately from `activity_date` (which we set to `period_start`).
- **Estimated reads** are common. UK suppliers mark readings as `ACTUAL` or `ESTIMATED`. Estimated reads are reconciled in a subsequent bill. This is why `meter_read_type` is captured and estimated reads get a suspicious flag.
- **UK business accounts** use MPAN (Meter Point Administration Number) as the meter identifier — a 13-digit code that uniquely identifies a supply point. US uses meter serial numbers.
- **Units**: Almost all portal exports are in kWh. Industrial accounts with >100kVA max demand may get MWh or GJ. We handle MWH and GJ conversion via UnitMapping (1 MWh = 1000 kWh, 1 GJ = 277.778 kWh).
- **Half-hourly metering**: Large commercial accounts (>100kW) are mandatory half-hourly (HH) metered in the UK. HH accounts show peak and off-peak splits. We capture these as optional fields.

### What our sample data looks like and why

`sample_data/utility_electricity.csv` contains 12 rows for 3 meters across 4 billing periods:

| Row | Scenario |
|---|---|
| MPAN-001/002/003 | Three different meters at three sites — exercises site mapping |
| Periods | All billing periods are non-calendar-month (e.g. Oct 17 → Nov 16) |
| MPAN-003 rows | `meter_read_type = ESTIMATED` — triggers suspicious flag |
| MPAN-002, Dec | Consumption of 5,800,000 kWh — absurdly high, triggers suspicious flag (threshold: 5M kWh) |
| MPAN-003, Jan | Negative consumption (−850 kWh) — fails parsing (negative consumption not allowed) |

The consumption figures for MPAN-001 (London HQ, ~50,000 kWh/month) are realistic for a medium office building. Manchester Plant (~115,000 kWh) is realistic for a light industrial site.

### What would break in a real deployment

1. **PDF invoices**: Many UK SME suppliers still only provide PDFs. No CSV export exists. Handling these requires OCR (we deliberately excluded this — see TRADEOFFS.md).
2. **Portal layout changes**: Utility portals redesign their export formats periodically. Our parser uses fuzzy column matching (alias lookup), which reduces brittleness, but a new column name we haven't mapped will be silently ignored.
3. **Currency conversion**: Our sample is GBP only. A multinational client with sites in EUR, USD, and GBP needs currency normalisation before financial aggregation.
4. **VAT handling**: UK electricity invoices include 5% VAT for business accounts. Our `total_amount` may be VAT-inclusive. For cost reporting you need ex-VAT figures. We don't split this.
5. **Reactive power / network charges**: Business electricity invoices include standing charges, reactive power charges, and distribution use-of-system (DUoS) charges. We capture only total consumption and total charge — the breakdown would require per-line invoice parsing.

---

## Source 3: Corporate Travel

### What we researched

We reviewed:
- **SAP Concur**: The Concur Expense Report Extract CSV is available from the admin portal under Intelligence > Standard Reports. Fields include expense type, traveler, dates, origin/destination, and amount. Concur sometimes includes distance (if the travel manager enabled it) but often does not.
- **Navan (formerly TripActions)**: The Navan Trips & Expenses export (admin portal) has near-identical shape. Navan tends to include flight distance more reliably than Concur.
- **DEFRA 2023 emission factors for travel**:
  - Flights: 0.1551 kg CO₂e/passenger-km (economy, including RFI), 0.4292 (business), 0.6209 (first)
  - Hotel stays: 20.8 kg CO₂e/room-night (average UK/Western Europe)
  - Car (average): 0.1714 kg CO₂e/km
  - National Rail: 0.0354 kg CO₂e/passenger-km

Key issues we found:
- **Distance is not always provided.** Concur records flights by origin/destination airport or city, but distance calculation requires a great-circle haul lookup table (airport IATA code → latitude/longitude → Haversine formula). We capture IATA codes and flag rows where distance is missing.
- **Expense type aliases vary.** Concur uses "Airfare"; Navan uses "Flight"; some clients configure custom types like "Air Travel" or "International Flight." We handle this via a keyword alias map.
- **Currency varies.** International travel involves hotel charges in local currency, flight charges in the booking currency. We capture the source currency and amount; FX conversion is out of scope.

### What our sample data looks like and why

`sample_data/corporate_travel.csv` contains 20 rows covering:

| Row | Scenario |
|---|---|
| EXP-2301 to 2304 | London–New York return trip (2 flights + 2 hotel nights) — exercises multi-row trip pattern |
| EXP-2305 to 2306 | Manchester train + taxi — exercises non-flight categories |
| EXP-2307 to 2308 | Frankfurt business class flight + 2-night hotel — exercises business class factor |
| EXP-2309 | Birmingham–Sheffield car rental — exercises CAR_RENTAL |
| EXP-2310 to 2311 | Dubai business class (long-haul) + 4-night hotel |
| EXP-2314 | London–Berlin flight without IATA codes — exercises missing-distance flag |
| EXP-2316 to 2317 | London–Singapore first class + 4 nights Sands — exercises high-value suspicious flag |
| EXP-2319 | Unknown traveler (blank name, blank email) — exercises missing traveler data |
| EXP-2320 | London–Sydney business class — longest route in sample |

All distances are real great-circle distances from airport reference data (LHR–JFK: 5,541 km; LHR–SIN: 10,847 km; LHR–SYD: 16,993 km).

### What would break in a real deployment

1. **Missing distances for flights**: Real Concur exports frequently omit distance. A production system needs an IATA-to-IATA distance lookup table (>10,000 airport pairs, or an API like OpenFlights). We flag these rows for manual entry — we do not estimate without data.
2. **Hotel emission factor granularity**: DEFRA's hotel factor (20.8 kg/room-night) is a global average. A real accounting would use region-specific factors (e.g. a Singapore hotel has a different grid intensity than a UK hotel). We use the single DEFRA figure.
3. **Radiative Forcing Index (RFI)**: DEFRA 2023 flight factors include RFI (×1.9 multiplier for non-CO₂ warming effects at altitude). Some clients exclude RFI per their auditor's instructions. Our factors include it — this needs to be a configurable toggle.
4. **Class of service mapping**: We map "BUSINESS" and "FIRST" — but Concur sometimes records "Business Class", "J Class", "Flat Bed Business", etc. Our alias map is not exhaustive.
5. **Per-diem and meals**: Concur expense reports include meals, per diems, and incidentals. We ignore these (no emission factor; not relevant for GHG reporting), but our parser would encounter them as UNKNOWN expense types and fail to classify them.
