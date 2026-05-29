# MODEL.md — Data Model Design

## Overview

The Emission Hub data model separates concerns cleanly into four layers:
**raw ingestion → normalization → review lifecycle → audit trail**.
Each layer is a distinct database table. Nothing is overwritten; everything is traceable.

---

## Entity Map

```
Tenant
  └── IngestionBatch (one per file upload)
        └── SourceRow (one per CSV row, immutable)
              └── NormalizedActivity (one-to-one with SourceRow, mutable until locked)
                    └── AuditEvent (many per activity, append-only)
```

Supporting tables: `UnitMapping`, `SiteMapping`, `EmissionFactor`

---

## Entities

### Tenant

Represents one client company. Every data-bearing table carries a `tenant` FK.

Multi-tenancy is row-level, not schema-level. We chose this because:
- A prototype needs to run on a single hosted database
- Row-level isolation is sufficient when all access goes through the API (which always scopes queries to the authenticated user's tenant)
- Schema-per-tenant adds operational complexity we deliberately excluded (see TRADEOFFS.md)

**Key fields:** `id` (UUID), `name`, `slug`, `country`, `industry`

---

### IngestionBatch

One record per file upload. Stores what came in, from which source, who sent it, and the outcome summary.

**Why separate from NormalizedActivity?**
Because the batch record answers "what upload produced this data?" independently of what the data actually said. If someone uploads the same file twice, you get two batches with two sets of activities — the analyst can compare them.

**Key fields:**
| Field | Purpose |
|---|---|
| `source_type` | `SAP`, `UTILITY`, or `TRAVEL` — which parser was used |
| `status` | `PENDING → PROCESSING → DONE / FAILED` |
| `total_rows` | Total rows in the file |
| `success_count` | Rows that parsed and normalized |
| `failed_count` | Rows that could not be parsed |
| `suspicious_count` | Rows that parsed but triggered validation flags |
| `uploaded_by` | Django User FK — who uploaded it |
| `file_name` / `file_size_bytes` | Provenance metadata |

---

### SourceRow

The raw CSV row, stored as a JSON dict (`raw_payload`). **Never mutated after creation.**

This is the source of truth for what the client actually sent. If our normalization logic had a bug and produced wrong output, we can fix the normalizer and re-process from SourceRow without asking the client to re-send anything. The raw data is never lost.

`parse_status` is either `PARSED` (row went through normalization) or `FAILED` (could not even be parsed into fields — e.g. wrong number of columns, unparseable date, missing mandatory field).

---

### NormalizedActivity

The central record analysts review. One per SourceRow (via OneToOne FK), nullable — manually entered records have no SourceRow.

**GHG Scope classification:**

| Scope | What it covers in this model |
|---|---|
| **Scope 1** | Direct combustion: `FUEL_DIESEL`, `FUEL_PETROL`, `FUEL_NATURAL_GAS`, `FUEL_LPG`, `FUEL_HFO` from SAP |
| **Scope 2** | Purchased electricity: `ELECTRICITY` from Utility source |
| **Scope 3** | Indirect: `FLIGHT`, `HOTEL`, `CAR_RENTAL`, `TRAIN`, `TAXI` from Travel; `PROCUREMENT` from SAP for non-fuel goods |

Scope is set deterministically from `category` by the normalization engine. Analysts can override it before approval.

**Quantity normalization design:**
We store both the original (`quantity`, `unit`) and the normalized (`normalized_quantity`, `normalized_unit`) values. This is deliberate — if our unit conversion was wrong, an auditor can see the original and the converted value and spot the error. We never silently replace source data.

**Review lifecycle:**

```
PENDING ──► APPROVED (locked_for_audit = True)
        └─► REJECTED
FLAGGED ──► APPROVED
        └─► REJECTED
```

`locked_for_audit = True` prevents any further edits. This mirrors real audit requirements: the record an auditor reviews must be identical to what the analyst approved.

**Key fields (abbreviated):**

| Field | Purpose |
|---|---|
| `category` | Activity type (FUEL_DIESEL, ELECTRICITY, FLIGHT, etc.) |
| `scope` | GHG Protocol scope (1, 2, 3) |
| `activity_date` | When the activity occurred |
| `period_start/end` | For utility billing periods that span calendar months |
| `site` / `raw_site_code` | Resolved site name + original code for traceability |
| `quantity` / `unit` | Original values from source |
| `normalized_quantity` / `normalized_unit` | After UnitMapping conversion |
| `co2e_kg` | Indicative CO₂e estimate — NOT audited, for analyst guidance only |
| `review_status` | PENDING / FLAGGED / APPROVED / REJECTED |
| `suspicious_flag` + `suspicious_reasons` | Auto-detected anomalies |
| `locked_for_audit` | True after approval — immutable |
| `approved_by` / `approved_at` | Who approved, when |
| `rejected_by` / `rejection_reason` | Rejection audit trail |

---

### AuditEvent

Append-only log. Every state change on a NormalizedActivity creates one row.

`before_json` and `after_json` store snapshots of the relevant fields at the moment of change. This means the audit log is self-contained — even if the model schema changes in a future migration, historical audit events still show what changed.

`actor` is NULL for system-generated events (ingestion pipeline). Human actions always have an actor.

**Actions tracked:** `INGEST`, `NORMALIZE`, `EDIT`, `APPROVE`, `REJECT`, `UNLOCK`

---

### UnitMapping

Translates source unit strings to a canonical unit with a numeric conversion factor.

**Why a database table and not code constants?**
Because unit aliases need to be correctable at runtime without a deployment. If a new client's SAP uses `LTR` instead of `L` for litres, an admin can add a row to this table without touching code.

Canonical units: `litres`, `kg`, `m3`, `kWh`, `km`

Example entries:
| source_unit | canonical_unit | factor |
|---|---|---|
| `KWH` | `kWh` | 1.0 |
| `MWH` | `kWh` | 1000.0 |
| `GJ` | `kWh` | 277.7778 |
| `L` | `litres` | 1.0 |
| `GAL` | `litres` | 3.78541 |
| `MI` | `km` | 1.60934 |
| `TO` | `kg` | 1000.0 |

---

### SiteMapping

Translates opaque source codes into human-readable site names.

SAP WERKS codes (`1000`, `2000`) mean nothing to an analyst without a lookup table. Utility MPAN numbers are similarly opaque. This table is seeded per-tenant during onboarding and can be extended by admins.

---

### EmissionFactor

Reference data: kg CO₂e per unit of activity, by category and year.
Sourced from **DEFRA 2023 GHG Conversion Factors for Company Reporting**.

Used for indicative estimates only. The `co2e_kg` field on NormalizedActivity is clearly labelled as non-audited. Full GHG accounting would require a separate calculation engine with market-based vs location-based electricity factors, radiative forcing indices, etc.

---

## Indexes

All high-traffic query patterns are indexed:
- `(tenant, source_type)` — scope/source filtering
- `(tenant, review_status)` — analyst workflow
- `(tenant, scope)` — GHG reporting
- `(suspicious_flag)` — flagged row view
- `(-created_at)` — recency ordering
- `(entity_type, entity_id)` on AuditEvent — per-record history lookup

---

## What this model does NOT handle

- **Calculated emissions reporting** — no aggregated report table. Analysts approve individual rows; report generation would consume the approved set.
- **Market-based Scope 2** — we use location-based only (UK grid average from DEFRA). Market-based requires supplier-specific emission factors.
- **Real-time sync** — no webhook or API polling. Upload-only for this prototype.
- **User roles / RBAC** — all authenticated users have analyst access. See TRADEOFFS.md.
