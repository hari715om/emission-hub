"""
Corporate travel CSV parser.

Format chosen: CSV export from Concur / Navan expense platform.
Justification: Both Concur (SAP) and Navan expose expense report exports
as CSV from their admin portals.  Concur's full OAuth2 API requires
enterprise credentials we can't simulate; the CSV export is what a
travel manager actually emails to the sustainability team monthly.
Navan's /reports endpoint returns near-identical shape.

Realistic column shape (based on Concur Expense Report extract and
Navan trip export documentation):
  expense_id          — unique row ID from the platform
  traveler_name       — full name
  traveler_email      — corporate email
  trip_start_date     — date trip began
  trip_end_date       — date trip ended
  expense_date        — date of the specific expense (e.g. flight booking date)
  expense_type        — FLIGHT, HOTEL, CAR_RENTAL, TRAIN, TAXI, RIDESHARE
  origin              — departure city/airport name
  destination         — arrival city/airport name
  origin_iata         — IATA airport code (e.g. LHR, JFK) — may be absent
  destination_iata    — IATA code at destination
  distance_km         — if available (Navan sometimes computes this)
  distance_miles      — alternative distance unit
  class_of_service    — ECONOMY, BUSINESS, FIRST (for flights)
                        or STANDARD, FIRST_CLASS (for trains)
  hotel_nights        — number of nights (for HOTEL rows)
  merchant_name       — airline / hotel chain / car rental company
  amount              — billable amount
  currency            — currency of amount
  booking_reference   — PNR or confirmation number
  purpose             — trip purpose (Business Dev, Client Meeting, etc.)
  department          — cost centre / department
  cost_centre         — SAP cost centre if company uses Concur-SAP integration

Emission factor approach:
  Flights: DEFRA 2023 kg CO2e/passenger-km by cabin class
  Hotels: DEFRA 2023 kg CO2e/room-night by region
  Car rental/taxi: DEFRA 2023 kg CO2e/km by vehicle type (assume average)
  Train: DEFRA 2023 kg CO2e/km (UK national rail average)

If distance_km is missing for flights, we flag the row as suspicious
(distance estimation from IATA codes is a non-trivial lookup table that
is outside scope — we record the airport codes and flag for manual entry).
"""
import csv
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger('ingestion')

COLUMN_ALIASES = {
    'expense_id': ['expense_id', 'expense id', 'id', 'report id', 'transaction id'],
    'traveler_name': ['traveler_name', 'traveler name', 'employee name', 'name', 'passenger'],
    'traveler_email': ['traveler_email', 'email', 'employee email', 'user email'],
    'expense_date': ['expense_date', 'expense date', 'date', 'transaction date', 'travel date'],
    'trip_start_date': ['trip_start_date', 'trip start', 'departure date', 'start date'],
    'trip_end_date': ['trip_end_date', 'trip end', 'return date', 'end date'],
    'expense_type': [
        'expense_type', 'expense type', 'type', 'category', 'travel type',
        'segment type', 'transport type'
    ],
    'origin': ['origin', 'from', 'departure', 'departure city', 'from city'],
    'destination': ['destination', 'to', 'arrival', 'arrival city', 'to city'],
    'origin_iata': ['origin_iata', 'origin iata', 'from iata', 'departure airport', 'origin code'],
    'destination_iata': [
        'destination_iata', 'destination iata', 'to iata',
        'arrival airport', 'destination code'
    ],
    'distance_km': ['distance_km', 'distance (km)', 'distance km', 'km', 'kilometres'],
    'distance_miles': ['distance_miles', 'distance (miles)', 'miles', 'mi'],
    'class_of_service': [
        'class_of_service', 'class of service', 'cabin', 'cabin class',
        'class', 'service class', 'fare class'
    ],
    'hotel_nights': ['hotel_nights', 'nights', 'number of nights', 'room nights'],
    'merchant_name': ['merchant_name', 'merchant', 'vendor', 'supplier', 'airline', 'hotel'],
    'amount': ['amount', 'cost', 'total', 'charge', 'billed amount'],
    'currency': ['currency', 'curr'],
    'booking_reference': ['booking_reference', 'booking ref', 'pnr', 'confirmation', 'reference'],
    'purpose': ['purpose', 'trip purpose', 'reason', 'business purpose'],
    'department': ['department', 'dept', 'business unit'],
    'cost_centre': ['cost_centre', 'cost center', 'cost centre', 'cc'],
}

DATE_FORMATS = [
    '%Y-%m-%d',
    '%d/%m/%Y',
    '%m/%d/%Y',
    '%d-%m-%Y',
    '%d %b %Y',
    '%d %B %Y',
    '%Y/%m/%d',
]

# Normalise expense type strings from various platforms to our categories
EXPENSE_TYPE_MAP = {
    'flight': 'FLIGHT',
    'flights': 'FLIGHT',
    'air': 'FLIGHT',
    'airfare': 'FLIGHT',
    'airline': 'FLIGHT',
    'hotel': 'HOTEL',
    'hotels': 'HOTEL',
    'accommodation': 'HOTEL',
    'lodging': 'HOTEL',
    'car rental': 'CAR_RENTAL',
    'car hire': 'CAR_RENTAL',
    'rental car': 'CAR_RENTAL',
    'vehicle rental': 'CAR_RENTAL',
    'train': 'TRAIN',
    'rail': 'TRAIN',
    'amtrak': 'TRAIN',
    'eurostar': 'TRAIN',
    'taxi': 'TAXI',
    'cab': 'TAXI',
    'rideshare': 'TAXI',
    'uber': 'TAXI',
    'lyft': 'TAXI',
    'ground': 'TAXI',
    'ground transport': 'TAXI',
}


def _build_alias_map(header: list[str]) -> dict[str, int]:
    alias_reverse = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_reverse[alias.lower().strip()] = canonical

    mapping = {}
    for i, col in enumerate(header):
        canonical = alias_reverse.get(col.lower().strip())
        if canonical:
            mapping[canonical] = i
    return mapping


def _parse_date(raw: str) -> Optional[str]:
    if not raw or not raw.strip():
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_decimal(raw: str) -> Optional[float]:
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip().replace(',', '').replace('$', '').replace('£', '').replace('€', '')
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(raw: str) -> Optional[int]:
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        return None


def _normalise_expense_type(raw: str) -> str:
    if not raw:
        return 'UNKNOWN'
    return EXPENSE_TYPE_MAP.get(raw.lower().strip(), 'UNKNOWN')


def parse_travel_csv(file_bytes: bytes) -> list[dict]:
    """
    Parse a corporate travel CSV export.

    Returns list of row dicts with keys: line_num, raw, parsed, error.
    """
    results = []
    text = file_bytes.decode('utf-8-sig', errors='replace')
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        return []

    header_idx = 0
    for i, row in enumerate(rows):
        if any(cell.strip() for cell in row):
            header_idx = i
            break

    header = rows[header_idx]
    col_map = _build_alias_map(header)

    def get(row: list, field: str) -> str:
        idx = col_map.get(field)
        if idx is None or idx >= len(row):
            return ''
        return row[idx].strip()

    for line_num, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not any(cell.strip() for cell in row):
            continue

        raw = {header[i]: row[i] for i in range(min(len(header), len(row)))}
        errors = []
        suspicious_reasons = []

        # Resolve date: prefer expense_date, fallback to trip_start_date
        raw_date = get(row, 'expense_date') or get(row, 'trip_start_date')
        activity_date = _parse_date(raw_date)
        if not activity_date:
            errors.append(f'Missing/invalid date: "{raw_date}"')

        expense_type_raw = get(row, 'expense_type')
        category = _normalise_expense_type(expense_type_raw)
        if category == 'UNKNOWN':
            errors.append(f'Unrecognised expense type: "{expense_type_raw}"')

        amount = _parse_decimal(get(row, 'amount'))
        currency = get(row, 'currency') or 'USD'

        origin = get(row, 'origin') or ''
        destination = get(row, 'destination') or ''
        origin_iata = get(row, 'origin_iata') or ''
        destination_iata = get(row, 'destination_iata') or ''

        dist_km_raw = get(row, 'distance_km')
        dist_miles_raw = get(row, 'distance_miles')
        distance_km = _parse_decimal(dist_km_raw)
        if distance_km is None and dist_miles_raw:
            miles = _parse_decimal(dist_miles_raw)
            if miles:
                distance_km = round(miles * 1.60934, 2)

        # Flag: flight without distance is suspicious — need it for emission calc
        if category == 'FLIGHT' and distance_km is None:
            suspicious_reasons.append(
                'Flight row missing distance — cannot compute Scope 3 without distance or IATA codes'
            )
            if not origin_iata or not destination_iata:
                suspicious_reasons.append('No IATA codes to estimate distance from')

        class_of_service = get(row, 'class_of_service') or ''
        hotel_nights = _parse_int(get(row, 'hotel_nights'))

        if category == 'HOTEL' and hotel_nights is None:
            suspicious_reasons.append('Hotel row missing number of nights')

        merchant = get(row, 'merchant_name') or ''
        booking_ref = get(row, 'booking_reference') or ''
        purpose = get(row, 'purpose') or ''
        department = get(row, 'department') or ''
        cost_centre = get(row, 'cost_centre') or ''
        traveler_name = get(row, 'traveler_name') or ''

        parsed = None if errors else {
            'activity_date': activity_date,
            'category': category,
            'scope': '3',
            'quantity': distance_km,
            'unit': 'km',
            'amount': amount,
            'currency': currency,
            'origin': origin,
            'destination': destination,
            'origin_iata': origin_iata,
            'destination_iata': destination_iata,
            'class_of_service': class_of_service,
            'hotel_nights': hotel_nights,
            'vendor': merchant,
            'reference_id': booking_ref,
            'description': purpose or f'{expense_type_raw} — {origin} to {destination}',
            'cost_centre': cost_centre,
            'department': department,
            'traveler_name': traveler_name,
            'suspicious_reasons': suspicious_reasons,
        }

        results.append({
            'line_num': line_num,
            'raw': raw,
            'parsed': parsed,
            'error': '; '.join(errors) if errors else None,
        })

    return results
