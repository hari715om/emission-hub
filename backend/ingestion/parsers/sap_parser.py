"""
SAP flat-file CSV parser.

Format chosen: SAP flat-file CSV export (transaction MB51 / ME2M / custom
extract via SM30).  Justification: IDoc is EDI-only, OData/BAPI require
active SAP connectivity we don't have in a file-upload prototype, and PDF
is non-machine-readable.  The flat-file CSV is what procurement teams actually
email to sustainability leads — it's the most realistic ingestion path.

Column reality:
  SAP uses German internal field names in some configurations.
  BUKRS = company code, WERKS = plant, LIFNR = vendor number,
  MATNR = material number, MAKTX = material description,
  MENGE = quantity, MEINS = unit of measure (SAP code),
  NETPR = net price, WAERS = currency, BLDAT = document date (YYYYMMDD),
  BKTXT = item text / header text, KOSTL = cost centre.

  In other configs, headers may be English labels instead of field names.
  We handle both via COLUMN_ALIASES below.

Date formats seen in real exports:
  YYYYMMDD (most common SAP internal format)
  DD.MM.YYYY (German locale format)
  DD/MM/YYYY (some localised outputs)
  MM/DD/YYYY (US locale outputs from some SAP instances)

We try all known formats before giving up.
"""
import csv
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger('ingestion')

# Maps the many column names SAP uses (German field codes, English labels,
# localised headers) to our internal canonical names.
COLUMN_ALIASES = {
    # Canonical name → list of known aliases (case-insensitive)
    'company_code': ['bukrs', 'company code', 'company_code', 'co code'],
    'plant': ['werks', 'plant', 'werk', 'plant code'],
    'vendor_number': ['lifnr', 'vendor', 'vendor number', 'vendor_number', 'lieferant'],
    'purchase_doc': ['ebeln', 'purchase document', 'po number', 'purchasing doc'],
    'material_doc': ['mblnr', 'material document', 'mat doc'],
    'material_number': ['matnr', 'material', 'material number', 'material_number'],
    'material_desc': ['maktx', 'material description', 'description', 'bezeichnung'],
    'quantity': ['menge', 'quantity', 'qty', 'menge in gme'],
    'unit': ['meins', 'unit', 'base unit', 'uom', 'einheit', 'unit of measure'],
    'net_price': ['netpr', 'net price', 'price', 'preis'],
    'price_unit': ['peinh', 'price unit', 'per'],
    'currency': ['waers', 'currency', 'curr', 'waehrung'],
    'document_date': ['bldat', 'document date', 'doc date', 'date', 'datum', 'belegdatum'],
    'posting_date': ['budat', 'posting date', 'buchungsdatum'],
    'item_text': ['bktxt', 'text', 'item text', 'header text', 'sgtxt', 'buchungstext'],
    'cost_centre': ['kostl', 'cost centre', 'cost center', 'kostenstelle'],
    'gl_account': ['hkont', 'gl account', 'g/l account', 'sachkonto'],
}

# Known SAP date formats in order of likelihood
DATE_FORMATS = [
    '%Y%m%d',    # 20231215 — SAP internal, most common
    '%d.%m.%Y',  # 15.12.2023 — German locale
    '%d/%m/%Y',  # 15/12/2023
    '%m/%d/%Y',  # 12/15/2023 — US locale
    '%Y-%m-%d',  # 2023-12-15 — ISO (some extracts)
    '%d-%m-%Y',  # 15-12-2023
]

# SAP material group → our activity category
MATERIAL_CATEGORY_MAP = {
    'diesel': 'FUEL_DIESEL',
    'gasoil': 'FUEL_DIESEL',
    'gas oil': 'FUEL_DIESEL',
    'petrol': 'FUEL_PETROL',
    'gasoline': 'FUEL_PETROL',
    'benzin': 'FUEL_PETROL',    # German
    'natural gas': 'FUEL_NATURAL_GAS',
    'erdgas': 'FUEL_NATURAL_GAS',  # German
    'lpg': 'FUEL_LPG',
    'flüssiggas': 'FUEL_LPG',
    'hfo': 'FUEL_HFO',
    'heavy fuel': 'FUEL_HFO',
    'schweres heizöl': 'FUEL_HFO',
}


def _build_alias_map(header_row: list[str]) -> dict[str, str]:
    """
    Given the actual CSV header row, return a mapping from
    canonical field name → column index position.
    """
    alias_reverse = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_reverse[alias.lower().strip()] = canonical

    mapping = {}
    for i, col in enumerate(header_row):
        canonical = alias_reverse.get(col.lower().strip())
        if canonical:
            mapping[canonical] = i
    return mapping


def _parse_date(raw: str) -> Optional[str]:
    """Try each known SAP date format; return ISO string or None."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_decimal(raw: str) -> Optional[float]:
    """Parse SAP numeric strings: handles comma-as-decimal-separator."""
    if not raw or not raw.strip():
        return None
    # SAP German locale uses period as thousands sep and comma as decimal
    cleaned = raw.strip().replace(' ', '')
    if ',' in cleaned and '.' in cleaned:
        # e.g. "1.234,56" → "1234.56"
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif ',' in cleaned:
        # e.g. "1234,56" → "1234.56"
        cleaned = cleaned.replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None


def _guess_category(desc: str, material: str) -> str:
    """Infer fuel category from material description and number."""
    combined = f'{desc} {material}'.lower()
    for keyword, category in MATERIAL_CATEGORY_MAP.items():
        if keyword in combined:
            return category
    return 'PROCUREMENT'


def parse_sap_csv(file_bytes: bytes) -> list[dict]:
    """
    Parse a SAP flat-file CSV upload.

    Returns a list of row dicts with keys:
      raw      — the original row as dict
      parsed   — normalized field values (or None on failure)
      error    — error message string (or None on success)
      line_num — 1-indexed line number in file
    """
    results = []
    text = file_bytes.decode('utf-8-sig', errors='replace')  # strip BOM if present
    reader = csv.reader(io.StringIO(text))

    rows = list(reader)
    if not rows:
        return []

    # Skip empty leading rows (SAP exports sometimes have a title row first)
    header_idx = 0
    for i, row in enumerate(rows):
        if any(cell.strip() for cell in row):
            header_idx = i
            break

    header = rows[header_idx]
    col_map = _build_alias_map(header)

    if not col_map:
        logger.warning('SAP parser: no recognised columns in header %s', header)

    def get(row: list, field: str) -> str:
        idx = col_map.get(field)
        if idx is None or idx >= len(row):
            return ''
        return row[idx].strip()

    for line_num, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not any(cell.strip() for cell in row):
            continue  # skip blank rows

        raw = {header[i]: row[i] for i in range(min(len(header), len(row)))}
        errors = []

        date_str = _parse_date(get(row, 'document_date') or get(row, 'posting_date'))
        if not date_str:
            errors.append(f'Unparseable date: "{get(row, "document_date")}"')

        qty_raw = get(row, 'quantity')
        qty = _parse_decimal(qty_raw)
        if qty is None and qty_raw:
            errors.append(f'Unparseable quantity: "{qty_raw}"')

        price_raw = get(row, 'net_price')
        price = _parse_decimal(price_raw)

        unit = get(row, 'unit') or ''
        currency = get(row, 'currency') or ''
        plant = get(row, 'plant') or ''
        material_desc = get(row, 'material_desc') or ''
        material_num = get(row, 'material_number') or ''
        vendor = get(row, 'vendor_number') or ''
        cost_centre = get(row, 'cost_centre') or ''
        item_text = get(row, 'item_text') or ''
        ref_id = get(row, 'material_doc') or get(row, 'purchase_doc') or ''

        category = _guess_category(material_desc, material_num)

        parsed = None if errors else {
            'activity_date': date_str,
            'quantity': qty,
            'unit': unit,
            'amount': price,
            'currency': currency,
            'raw_site_code': plant,
            'category': category,
            'vendor': vendor,
            'description': material_desc or item_text,
            'reference_id': ref_id,
            'cost_centre': cost_centre,
        }

        results.append({
            'line_num': line_num,
            'raw': raw,
            'parsed': parsed,
            'error': '; '.join(errors) if errors else None,
        })

    return results
