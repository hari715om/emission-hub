"""
Utility electricity CSV parser.

Format chosen: utility portal CSV export.
Justification: UK business electricity suppliers (EDF, British Gas, Octopus
Business, SSE) and US utilities (PG&E, Con Ed, Ameren) all offer CSV downloads
from their online business portals. PDFs require OCR (out of scope). Smart
meter APIs (e.g. DCC, ESME) require meter registration and are facility-team
work, not an ingestion-prototype concern.

Realistic column shape (based on actual UK/US utility portal exports):
  meter_id            — MPAN (UK) or meter serial number (US)
  site_name           — what the portal labels the account/location
  billing_period_start, billing_period_end — ISO dates (portals usually export these)
  consumption_kwh     — total consumption for the period
  peak_kwh            — peak consumption (optional, HH metering)
  off_peak_kwh        — off-peak (optional, Economy 7 or ToU tariff)
  demand_kw           — max demand for period (commercial accounts)
  tariff_name         — e.g. "Standard Variable", "Fixed Rate 2023"
  unit_rate_pence     — pence per kWh (UK) or cents/kWh (US)
  standing_charge     — fixed charge for period
  vat_amount          — VAT (UK) or tax
  total_amount        — total invoice amount
  currency            — GBP, USD, EUR, etc.
  meter_read_type     — ACTUAL or ESTIMATED

Key reality: billing periods do NOT align with calendar months.
A meter read might run 15 Jan to 16 Feb. We store period_start and
period_end separately and use period_start as activity_date for
filtering purposes.

Units: almost always kWh from portals, but some industrial accounts
get MWh or GJ. We handle the conversion via UnitMapping.
"""
import csv
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger('ingestion')

COLUMN_ALIASES = {
    'meter_id': ['meter_id', 'meter id', 'mpan', 'meter serial', 'account number', 'meter reference'],
    'site_name': ['site_name', 'site name', 'site', 'location', 'premises', 'address'],
    'period_start': ['billing_period_start', 'period start', 'start date', 'from date', 'from', 'bill from'],
    'period_end': ['billing_period_end', 'period end', 'end date', 'to date', 'to', 'bill to'],
    'consumption_kwh': [
        'consumption_kwh', 'consumption (kwh)', 'kwh', 'usage kwh', 'total kwh',
        'units consumed', 'consumption', 'energy kwh', 'net kwh'
    ],
    'peak_kwh': ['peak_kwh', 'peak kwh', 'day kwh', 'day units'],
    'off_peak_kwh': ['off_peak_kwh', 'off peak kwh', 'night kwh', 'night units'],
    'demand_kw': ['demand_kw', 'max demand', 'maximum demand (kw)', 'kva demand'],
    'consumption_unit': ['unit', 'units', 'consumption unit', 'uom'],
    'tariff_name': ['tariff_name', 'tariff', 'rate plan', 'product', 'rate code'],
    'unit_rate': ['unit_rate', 'unit rate', 'rate', 'p/kwh', 'c/kwh', 'price per kwh'],
    'standing_charge': ['standing_charge', 'standing charge', 'daily charge', 'fixed charge'],
    'total_amount': ['total_amount', 'total', 'amount', 'invoice total', 'bill amount', 'charge'],
    'currency': ['currency', 'curr'],
    'read_type': ['meter_read_type', 'read type', 'type', 'estimated', 'actual/estimated'],
}

DATE_FORMATS = [
    '%Y-%m-%d',  # ISO (portals prefer this)
    '%d/%m/%Y',  # UK standard
    '%m/%d/%Y',  # US standard
    '%d-%m-%Y',
    '%d %b %Y',  # 15 Jan 2023
    '%d %B %Y',  # 15 January 2023
    '%Y/%m/%d',
]


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
    cleaned = raw.strip().replace(',', '').replace('£', '').replace('$', '').replace('€', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_utility_csv(file_bytes: bytes) -> list[dict]:
    """
    Parse a utility portal CSV export.

    Returns list of row dicts with keys: line_num, raw, parsed, error.
    """
    results = []
    text = file_bytes.decode('utf-8-sig', errors='replace')
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        return []

    # Find header — first non-empty row
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

        period_start = _parse_date(get(row, 'period_start'))
        period_end = _parse_date(get(row, 'period_end'))

        if not period_start:
            errors.append(f'Missing/invalid period start: "{get(row, "period_start")}"')
        if not period_end:
            errors.append(f'Missing/invalid period end: "{get(row, "period_end")}"')

        kwh_raw = get(row, 'consumption_kwh')
        consumption = _parse_decimal(kwh_raw)
        # Default unit from portal is kWh; override if explicit unit column present
        consumption_unit = get(row, 'consumption_unit') or 'kWh'

        if consumption is None:
            errors.append(f'Missing/invalid consumption: "{kwh_raw}"')
        elif consumption < 0:
            errors.append('Negative consumption value')

        amount_raw = get(row, 'total_amount')
        amount = _parse_decimal(amount_raw)
        currency = get(row, 'currency') or 'GBP'
        meter_id = get(row, 'meter_id') or ''
        site_name = get(row, 'site_name') or ''
        tariff = get(row, 'tariff_name') or ''
        read_type = get(row, 'read_type') or 'ACTUAL'

        is_estimated = 'estim' in read_type.lower()

        parsed = None if errors else {
            'activity_date': period_start,
            'period_start': period_start,
            'period_end': period_end,
            'quantity': consumption,
            'unit': consumption_unit,
            'amount': amount,
            'currency': currency,
            'raw_site_code': meter_id,
            'site': site_name,
            'category': 'ELECTRICITY',
            'scope': '2',
            'description': tariff,
            'reference_id': meter_id,
            'is_estimated': is_estimated,
        }

        results.append({
            'line_num': line_num,
            'raw': raw,
            'parsed': parsed,
            'error': '; '.join(errors) if errors else None,
        })

    return results
