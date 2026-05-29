# DECISIONS.md — Every Ambiguity Resolved

This document records every significant decision made during the build, what was chosen, why, and what we would ask the PM if we had the chance.

---

## 1. SAP export format — why flat-file CSV, not IDoc or OData

**Ambiguity:** SAP exposes data in many ways: IDocs (EDI), OData services (SAP Gateway), BAPIs (RFC calls), ABAP report flat files, or transaction-level CSV exports (e.g., MB51 material documents, ME2M purchase orders).

**Decision:** Flat-file CSV from SAP transaction exports (MB51 / ME2M / custom ABAP report via SM30).

**Why:**
- IDoc is an EDI integration format. It requires an EDI middleware layer (SAP PI/PO or a third-party adapter). A sustainability team does not have this set up — IDocs go to logistics partners, not to ESG tools.
- OData/BAPI require live SAP connectivity with an RFC user, SSL, and firewall rules. We have none of that in a prototype, and most clients won't expose SAP directly to a SaaS product without months of procurement/security review.
- The flat-file CSV is what a business analyst actually exports and emails to the sustainability lead every month. It is the realistic ingestion path for an enterprise that is not yet doing real-time integration.

**What we ignore:** Real-time SAP integration, IDoc structure, OData delta tokens, RFC connection pooling.

**What we'd ask the PM:** "Does the client have a sustainability analyst who exports from SAP manually, or do they have a middleware team who can set up an OData feed? The answer changes the architecture entirely."

---

## 2. Utility data — why portal CSV, not PDF or smart meter API

**Ambiguity:** Electricity data arrives as PDF invoices, portal CSV downloads, or (for smart meters) via the UK DCC/ESME API or US Green Button API.

**Decision:** Portal CSV export from the supplier's business portal.

**Why:**
- PDF requires OCR. OCR on invoices has error rates that make it unsuitable for audited data without human review of every extracted value. It is also highly supplier-specific (EDF's PDF layout ≠ British Gas's). This is a can of worms for a 4-day prototype.
- Smart meter APIs (DCC in the UK, Green Button in the US) require meter registration, OAuth flows, and in some cases physical meter provisioning. A facilities team typically does not have API credentials for their meters — they log into a portal and click "Export CSV".
- Portal CSV is what a real facilities manager actually does. The CSV from EDF's business portal, British Gas's Evolve platform, or Octopus Business contains exactly the fields we need: meter ID, billing period, kWh, amount.

**What we ignore:** PDF ingestion, smart meter half-hourly data (we use billing-period totals), Green Button XML format.

**What we'd ask the PM:** "Does the facilities team have credentials for the utility's business portal? Can they export a CSV? If not, do we have PDF invoices, and is OCR acceptable given its error rate?"

---

## 3. Travel data — why Concur/Navan CSV, not live API

**Ambiguity:** Concur (SAP Concur) and Navan both have REST APIs. But they also both offer CSV exports from their admin/reporting portals.

**Decision:** CSV export from the travel platform's expense reporting module.

**Why:**
- Concur's API requires OAuth2 with enterprise app registration, scope approvals from the client's IT admin, and in some regions a Concur Partner certification. A 4-day prototype cannot get past that procurement gate.
- Navan's `/reports` endpoint is cleaner but still requires API key provisioning per client.
- The CSV export is what a travel manager generates for month-end reconciliation. It is the file that lands in the sustainability lead's inbox.
- The shape is nearly identical between platforms — both export expense type, traveler, origin, destination, amount, and (sometimes) distance.

**What we ignore:** Real-time booking webhooks, Concur's TripIt integration, hotel carbon reporting via HCMI.

**What we'd ask the PM:** "Who owns the Concur/Navan admin account? Can they set up a recurring report export? Or do we need to pursue API integration via their IT team?"

---

## 4. Scope classification — deterministic from category, not analyst-assigned

**Decision:** Scope is set by the normalization engine based on activity category. Analysts can override it before approval.

**Why:** Making analysts manually assign scope to every row would be slow and error-prone. The GHG Protocol mapping is deterministic for the categories we handle:
- Diesel/petrol/gas combustion at owned facilities = Scope 1
- Purchased electricity = Scope 2
- Business travel, hotels, procurement = Scope 3

**Exception:** SAP procurement rows for non-fuel goods are Scope 3 by default and flagged for analyst review, because the scope depends on how the goods are used (raw materials for a product = upstream Scope 3; office supplies = also Scope 3 but different category 1 vs 7).

---

## 5. CO₂e estimates — indicative only, not audited

**Decision:** We compute indicative CO₂e using DEFRA 2023 emission factors and store it in `co2e_kg`, clearly labelled as non-audited.

**Why:** The assignment says to ingest and normalize data so analysts can review it before it "goes to auditors." The auditors want the underlying activity data (kWh, litres, km), not just a CO₂e number. CO₂e calculation is a separate step that uses approved activity data plus agreed emission factors. We compute an estimate to help analysts spot anomalies (a flight that shows 50,000 kg CO₂e is probably wrong), but we do not present it as the audited figure.

**What we'd ask the PM:** "What emission factor methodology has the client agreed to use? DEFRA location-based? Market-based with supplier-specific REGOs? GHG Protocol Scope 2 Guidance market-based?"

---

## 6. Authentication — session-based, not JWT

**Decision:** Django's built-in session authentication, exposed via `/api/auth/login/` and `/api/auth/me/`.

**Why:** JWT requires token storage decisions (localStorage is XSS-vulnerable; httpOnly cookies work but then you need CSRF protection anyway, which is what sessions already give you). For a prototype with a single deployment and no mobile clients, Django sessions are simpler, more secure by default, and require zero additional libraries. JWT would add complexity without benefit here.

**What we'd ask the PM:** "Will this be used by mobile apps or third-party integrations that can't use cookies? If yes, we should revisit JWT with httpOnly refresh tokens."

---

## 7. Synchronous vs async ingestion

**Decision:** Ingestion runs synchronously in the request/response cycle. No Celery.

**Why:** The sample files are under 20 MB. Parsing a 1,000-row CSV in Python takes under a second. Celery would add Redis, a worker process, and deployment complexity for no practical benefit at this file size. The implementation plan explicitly flagged this as optional: "optional Celery only if async parsing becomes necessary."

**Tradeoff acknowledged:** A file with 100,000 rows would timeout the HTTP request. See TRADEOFFS.md.

---

## 8. Unit of measure normalization — database table, not code constants

**Decision:** `UnitMapping` is a database table, seeded by fixture, correctable at runtime.

**Why:** Unit aliases vary by client. One client's SAP may output `LTR`, another's `L`, another's `LITRE`. Fixing this should not require a code deployment — an admin should be able to add a mapping row. The database table allows this; hardcoded constants do not.

---

## 9. Site mapping — per-tenant lookup table, not embedded in parser

**Decision:** `SiteMapping` table per tenant, seeded during onboarding.

**Why:** SAP plant codes (`WERKS`) are meaningless without a lookup table. Code `1000` means London HQ at Acme Corp but means something completely different at another client. The mapping must be tenant-specific and configurable without code changes. We seed it for the demo tenant; production would import it from the client's SAP plant master data.

---

## 10. What we would ask the PM before building version 2

1. "What emission factor methodology has the client agreed to with their auditor — DEFRA, EPA, or a custom set?"
2. "Does the client want market-based or location-based Scope 2 accounting?"
3. "Is there a GHG Protocol boundary — operational control or equity share?"
4. "Who are the named analysts? Do we need role separation (uploader cannot approve their own upload)?"
5. "What is the client's reporting period — calendar year or financial year?"
6. "Are we expected to produce a GHG inventory report from this tool, or just feed data into their existing reporting platform?"
7. "Does the client have a system integrator who can set up an OData feed from SAP, or will it always be CSV?"
