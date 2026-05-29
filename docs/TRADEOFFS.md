# TRADEOFFS.md — What We Deliberately Did Not Build

This document describes three things we chose not to build, and why. These are not oversights — they are deliberate scope decisions that let us ship something sharp and defensible in four days.

---

## 1. Asynchronous ingestion pipeline (no Celery / Redis)

**What it would do:** Move file parsing and normalization off the HTTP request thread into a background task queue. The upload endpoint would return a `202 Accepted` immediately, and the client would poll for the batch status.

**Why we didn't build it:**
- The assignment's sample data is small (tens to hundreds of rows). A 500-row CSV parses in under 100ms. Celery would add Redis, a separate worker process, deployment configuration, task monitoring, and retry logic for zero practical benefit at this scale.
- The implementation plan explicitly tagged Celery as "optional only if async parsing becomes necessary."
- A synchronous pipeline is easier to reason about, test, and debug. When something goes wrong during ingestion, the error is in the HTTP response — not buried in a task log.

**What breaks in production:**
A file with 50,000 rows would take several seconds to process and would hit the HTTP timeout of most reverse proxies (typically 30–60 seconds). A production system would need async processing for large files.

**How we'd add it:**
Replace the `_run_ingestion()` function body with a Celery `delay()` call. The batch `status` field is already designed for async polling (`PENDING → PROCESSING → DONE`). The DB schema requires no changes — only the view and task code changes.

---

## 2. Role-based access control (no RBAC)

**What it would do:** Separate permissions for uploaders, reviewers, and auditors. An uploader should not be able to approve their own upload (segregation of duties). An auditor should have read-only access to locked records. A tenant admin should manage site mappings and user access.

**Why we didn't build it:**
- Django's permission system can support this but it requires careful design, custom permission classes, and testing across every endpoint.
- The assignment says "10% analyst UX." A working, intuitive analyst workflow for a single analyst role is more valuable than a broken multi-role system.
- The GHG Protocol's segregation-of-duties requirement (uploader ≠ approver) is real, but in a prototype the reviewer is the same person evaluating the tool — collapsing roles for evaluation purposes is appropriate.

**What breaks in production:**
Any organization with more than one person touching data needs role separation. An uploader approving their own data is a control failure in any audited GHG inventory.

**How we'd add it:**
Three Django Groups: `uploader` (can POST to ingestion endpoints), `analyst` (can PATCH activities and POST approve/reject), `auditor` (read-only on all endpoints). Custom `IsAnalyst`, `IsAuditor` permission classes. The `locked_for_audit` flag already prevents edits after approval — the role layer would prevent unauthorized approvals.

---

## 3. GHG inventory report generation

**What it would do:** Aggregate approved NormalizedActivity rows into a structured GHG inventory report — total Scope 1/2/3 emissions by category, by period, by site — exportable as PDF or Excel for submission to auditors or CDP.

**Why we didn't build it:**
- The assignment says to "ingest, normalize, and let analysts review and sign off before it goes to auditors." The deliverable is the review workflow, not the report.
- Report generation requires decisions we haven't made with the client: reporting boundary (operational control vs equity share), emission factor vintage year, market-based vs location-based Scope 2, currency for financial reporting. Building a report before those are agreed would produce a number the client couldn't use.
- A working report that uses wrong methodology is worse than no report.

**What breaks in production:**
Without a report, the auditors receive a database export or a CSV of approved rows. They would need to aggregate this themselves. That's acceptable for a prototype handoff but not for production.

**How we'd add it:**
A `/api/v1/reports/generate/` endpoint that runs a GROUP BY query on approved NormalizedActivity rows filtered by `(tenant, period_start, period_end)`, multiplies normalized quantities by EmissionFactor values, and returns a structured JSON that a React page can render as a summary table with an Excel download (using the `openpyxl` library already available in the ecosystem).

---

## Honourable mentions (things we also skipped)

| Skipped | Why |
|---|---|
| PDF invoice parsing (OCR) | Error rates unacceptable for audited data without extensive validation |
| Real SAP OData/RFC integration | Requires live SAP credentials, firewall access, months of procurement |
| Live Concur / Navan API | Requires OAuth2 enterprise app registration per client |
| Multi-factor authentication | Out of scope for a prototype — session auth is sufficient |
| Soft-delete / record archiving | Not needed at prototype scale |
| Webhook-based data push | Async complexity without client API to push to |
| Automated test suite | Deliberate tradeoff — the time went into a realistic data model and parser logic |
| Email notifications | No SMTP configured; not in the assignment scope |
