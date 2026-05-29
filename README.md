# Emission Hub — Breathe ESG Intern Assignment

A Django REST + React prototype for ingesting, normalizing, and analyst-reviewing ESG emissions data from three realistic enterprise source types.

**Live demo:** `[add URL after deployment]`
**Admin credentials:** `admin / breathe123`

---

## What it does

- **Ingest** CSV files from SAP (fuel/procurement), utility portals (electricity), and travel platforms (Concur/Navan)
- **Normalize** raw rows into a common activity schema with GHG Scope 1/2/3 classification
- **Flag** suspicious rows automatically (anomalous values, missing data, unknown codes)
- **Review** — analysts see raw vs. normalized data side by side, edit fields, approve or reject rows
- **Lock** approved rows for audit — immutable once signed off
- **Audit trail** — every edit, approval, and rejection is logged with actor and timestamp

---

## Project structure

```
emission-hub/
  backend/          Django REST API
  frontend/         React (Vite) analyst dashboard
  docs/             MODEL.md  DECISIONS.md  TRADEOFFS.md  SOURCES.md
  sample_data/      Realistic CSV files for testing
```

---

## Local development

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # Edit if needed (SQLite works with defaults)

python manage.py migrate
python manage.py seed_demo    # Creates admin user + demo tenant + reference data

python manage.py runserver
```

API available at: `http://localhost:8000/api/v1/`
Admin panel: `http://localhost:8000/admin/`

### Frontend

```bash
cd frontend
npm install
cp .env.example .env          # Leave VITE_API_URL blank for local proxy

npm run dev
```

App available at: `http://localhost:5173`

---

## Uploading sample data

1. Log in at `http://localhost:5173` with `admin / breathe123`
2. Go to **Upload Data**
3. Upload `sample_data/sap_fuel_procurement.csv` → SAP source
4. Upload `sample_data/utility_electricity.csv` → Utility source
5. Upload `sample_data/corporate_travel.csv` → Travel source
6. Go to **Review & Approve** to see normalized rows, suspicious flags, and the approval workflow

---

## API overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login/` | Session login |
| GET | `/api/auth/me/` | Current user |
| POST | `/api/v1/ingestion/sap/upload/` | Upload SAP CSV |
| POST | `/api/v1/ingestion/utility/upload/` | Upload utility CSV |
| POST | `/api/v1/ingestion/travel/upload/` | Upload travel CSV |
| GET | `/api/v1/batches/` | List ingestion batches |
| GET | `/api/v1/activities/` | List normalized activities (filterable) |
| PATCH | `/api/v1/activities/{id}/` | Edit activity |
| POST | `/api/v1/activities/{id}/approve/` | Approve row |
| POST | `/api/v1/activities/{id}/reject/` | Reject with reason |
| POST | `/api/v1/activities/bulk-approve/` | Approve multiple rows |
| GET | `/api/v1/activities/{id}/history/` | Audit trail for row |
| GET | `/api/v1/dashboard/stats/` | Dashboard summary numbers |
| GET | `/api/v1/audit-events/` | Full audit log |

---

## Documentation

| File | Contents |
|------|----------|
| [MODEL.md](docs/MODEL.md) | Data model design, entity relationships, GHG scope classification, index strategy |
| [DECISIONS.md](docs/DECISIONS.md) | Every ambiguity resolved — SAP format, utility portal vs PDF, travel CSV vs API, auth choice |
| [TRADEOFFS.md](docs/TRADEOFFS.md) | Three deliberate non-builds with production impact and how we'd add them |
| [SOURCES.md](docs/SOURCES.md) | Research behind each source format, sample data justification, production failure modes |

---

## Deployment (Render)

See `render.yaml` for Render Blueprint configuration.

Backend: Python/Django web service + PostgreSQL
Frontend: Static site (Vite build)

```bash
# Build frontend for production
cd frontend && npm run build

# Deploy backend
cd backend && gunicorn emission_hub.wsgi:application
```

---

## Tech stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Django 4.2 + Django REST Framework | Batteries included — auth, ORM, admin, serializers |
| Database | PostgreSQL (SQLite for dev) | JSONB for raw_payload, strong ACID for audit trail |
| Frontend | React 18 + Vite | Fast HMR, simple build pipeline |
| Routing | React Router v6 | URL-based filter state for analyst workflow |
| HTTP | Axios | CSRF interceptor, clean error handling |
| Styling | Vanilla CSS | Full control, no framework lock-in |
| Deployment | Render | Free tier, Postgres included, blueprint support |

---

## Grading criteria addressed

| Criterion | Where to look |
|-----------|--------------|
| Data model quality (35%) | `docs/MODEL.md`, `backend/normalization/models.py`, `backend/ingestion/models.py` |
| Decision defense (25%) | `docs/DECISIONS.md` |
| Source realism (20%) | `docs/SOURCES.md`, `backend/ingestion/parsers/`, `sample_data/` |
| Analyst UX (10%) | `frontend/src/pages/ReviewTable.jsx`, `ActivityDrawer.jsx` |
| Tradeoffs (10%) | `docs/TRADEOFFS.md` |
