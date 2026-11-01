# EventPrice Intelligence — FastAPI Backend

Modular, production-ready FastAPI backend foundation with SQLAlchemy 2.x and Alembic migrations for the EventPrice Intelligence platform.

---

## 🏗️ Architecture & Structure

```
backend/
├── alembic/                 # Alembic migration environment and versions
│   ├── env.py               # Dynamic Alembic environment bound to app settings
│   ├── script.py.mako       # Migration template
│   └── versions/            # Database schema migration revisions
├── alembic.ini              # Alembic root configuration
├── app/
│   ├── __init__.py
│   ├── main.py              # Application factory, lifespan, CORS, and exception handlers
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Pydantic BaseSettings & environment variable parsing
│   │   └── database.py      # SQLAlchemy 2.x Base, engine, SessionLocal & get_db dependency
│   └── api/
│       ├── __init__.py
│       └── routes/
│           ├── __init__.py
│           └── health.py    # GET /health operational endpoint
├── tests/
│   ├── __init__.py
│   ├── test_database.py     # Engine connection, session lifecycle & URL switchability tests
│   └── test_health.py       # Automated endpoint & CORS test coverage
├── .env                     # Local active environment variables (excluded from git)
├── .env.example             # Template environment variables
├── .gitignore               # Python, SQLite (*.db), venv, and cache exclusions
├── requirements.txt         # Pinned backend dependencies
└── README.md                # Backend setup guide
```

---

## 🚀 Setup & Execution Guide (Windows)

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.14)
- **PowerShell** or **Command Prompt**

### 2. Virtual Environment Setup

Navigate to the `backend/` directory:

```powershell
cd backend
```

Create and activate a Python virtual environment:

**PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Command Prompt (cmd):**
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create your local `.env` file from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Key environment configurations available:
- `APP_NAME`: Name displayed in API responses and docs
- `APP_VERSION`: Current semantic version
- `ENVIRONMENT`: `development` | `staging` | `production`
- `DEBUG`: `True` | `False`
- `DATABASE_URL`: Database connection string (`sqlite:///./eventprice.db` for local SQLite; switchable to PostgreSQL via `postgresql+psycopg://user:password@host:port/dbname` using the included psycopg 3 driver without application code modifications)
- `DB_ECHO_LOG`: `True` | `False` (Logs SQL statements when enabled)
- `HOST`: Server bind address (`127.0.0.1`)
- `PORT`: Server listen port (`8000`)
- `CORS_ORIGINS`: Allowed web client origins (`["http://localhost:5173"]`)
- `SECRET_KEY`: Backend secret key loaded strictly via environment variables

---

## 🗄️ Database & Alembic Migrations

The database foundation uses **SQLAlchemy 2.x** with a Declarative Base and request-scoped session dependency (`get_db`).

### Running Migrations

From the `backend/` directory with virtual environment activated:

```powershell
# Check current migration revision
alembic current

# Generate new migration when models change in future phases
alembic revision --autogenerate -m "migration_description"

# Apply migrations to database
alembic upgrade head
```

---

## 🏃 Running the Development Server

From inside the `backend/` directory:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Or from the repository root:

```powershell
$env:PYTHONPATH="backend"
.\backend\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The server will be available at:
- **API Root**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 📡 API Endpoints

### Health Endpoints
- `GET /health` — Service health check
- `GET /api/v1/health` — Versioned health check

### Event & Requirements Endpoints (`/api/v1/events`)
- `POST /api/v1/events/` — Create new event
- `GET /api/v1/events/` — List events with pagination (`skip`, `limit`, `status`, `city` filters)
- `GET /api/v1/events/{event_id}` — Retrieve event with its requirements (uses `selectinload` to prevent N+1 queries)
- `PATCH /api/v1/events/{event_id}` — Partially update event
- `DELETE /api/v1/events/{event_id}` — Delete event (cascades deletion to requirements)
- `POST /api/v1/events/{event_id}/requirements` — Add requirement line item
- `PATCH /api/v1/events/{event_id}/requirements/{requirement_id}` — Update requirement (validates event ownership)
- `DELETE /api/v1/events/{event_id}/requirements/{requirement_id}` — Delete requirement (validates event ownership)

### Vendor & Service Endpoints (`/api/v1/vendors`)
- `POST /api/v1/vendors/` — Register new vendor (defaults to `unverified`; public self-verification is strictly prohibited)
- `GET /api/v1/vendors/` — List vendors with pagination and filters (`city`, `vendor_type`, `verification_status`, `is_active`, `category`)
- `GET /api/v1/vendors/{vendor_id}` — Retrieve vendor with service catalog (uses `selectinload` to prevent N+1 queries)
- `PATCH /api/v1/vendors/{vendor_id}` — Partially update vendor profile (cannot set verification status to `verified`)
- `DELETE /api/v1/vendors/{vendor_id}` — Delete vendor (cascades deletion to all services and price records)
- `POST /api/v1/vendors/{vendor_id}/services` — Add service offering to vendor catalog
- `PATCH /api/v1/vendors/{vendor_id}/services/{service_id}` — Update service offering (validates vendor ownership)
- `DELETE /api/v1/vendors/{vendor_id}/services/{service_id}` — Delete service offering (validates vendor ownership)

### Price Records & Evidence Endpoints (`/api/v1/prices`)
- `POST /api/v1/prices/` — Record new price observation (validates vendor and service co-ownership, currency code, quantity bounds, tax rates, and optional initial evidence)
- `GET /api/v1/prices/` — List price observations with pagination (`skip`, `limit`) and filters (`vendor_id`, `vendor_service_id`, `event_id`, `currency`, `price_type`, `availability_status`)
- `GET /api/v1/prices/{price_id}` — Retrieve price observation with eager-loaded evidence records and parent entity names
- `PATCH /api/v1/prices/{price_id}` — Partially update descriptive/status fields (`tax_included`, `tax_rate`, `valid_from`, `valid_until`, `availability_status`, `availability_checked_at`, `minimum_quantity`, `maximum_quantity`). Financial values (`amount`, `currency`, `unit`, `vendor_id`, `vendor_service_id`) are immutable to prevent silent history overwrites.
- `POST /api/v1/prices/{price_id}/evidence` — Attach supporting evidence (source URL, quote author, validity period, inclusions, exclusions, notes)
- `GET /api/v1/prices/{price_id}/evidence` — List all evidence records for a price observation ordered chronologically descending
- `GET /api/v1/prices/vendors/{vendor_id}/history` — Retrieve complete historical pricing observations for a vendor
- `GET /api/v1/prices/services/{service_id}/comparison` — Service price comparison classified into buckets (`published_prices`, `vendor_quotations`, `vendor_confirmed`, `estimates`, `expired`, `unknown`). *Confirmed rates strictly require `vendor_confirmed` evidence.*

### Event Budget, Line Items & Scenarios Endpoints (`/api/v1/events/{event_id}/budgets`)
- `POST /api/v1/events/{event_id}/budgets/` — Create new event budget with allocated ceiling, contingency percentage, and tax calculation policy
- `GET /api/v1/events/{event_id}/budgets/` — List all budgets for an event
- `GET /api/v1/events/{event_id}/budgets/{budget_id}` — Retrieve budget details with eager-loaded line items
- `PATCH /api/v1/events/{event_id}/budgets/{budget_id}` — Update budget configuration parameters
- `DELETE /api/v1/events/{event_id}/budgets/{budget_id}` — Delete budget (cascades deletion to line items and scenarios)
- `POST /api/v1/events/{event_id}/budgets/{budget_id}/items` — Add line item (supports snapshotted financial figures from linked vendor price records)
- `PATCH /api/v1/events/{event_id}/budgets/{budget_id}/items/{item_id}` — Update line item figures and annotations
- `DELETE /api/v1/events/{event_id}/budgets/{budget_id}/items/{item_id}` — Delete line item
- `GET /api/v1/events/{event_id}/budgets/{budget_id}/summary` — Calculate deterministic financial breakdown (subtotals, tax breakdown, discounts, contingency buffer, category aggregates, budget utilization)
- `POST /api/v1/events/{event_id}/budgets/{budget_id}/scenarios` — Create budget scenario (supports cloning baseline items or custom scenario assumptions)
- `GET /api/v1/events/{event_id}/budgets/{budget_id}/scenarios` — List budget scenarios
- `GET /api/v1/events/{event_id}/budgets/{budget_id}/scenarios/compare` — Compare scenarios side-by-side against baseline budget and allocated ceiling

### Task Management, Timeline & Dependencies Endpoints (`/api/v1/events/{event_id}/tasks`)
- `POST /api/v1/events/{event_id}/tasks/` — Create a new task scoped to an event. Supports exact categories (`planning`, `venue`, `catering`, `photography`, `decoration`, `entertainment`, `transport`, `accommodation`, `finance`, `invitations`, `logistics`, `other`), statuses (`pending`, `in_progress`, `blocked`, `completed`, `cancelled`), and priorities (`low`, `medium`, `high`, `critical`). Auto-records initial audit activity.
- `GET /api/v1/events/{event_id}/tasks/` — List active tasks with pagination (`skip`, `limit`) and filters (`status`, `priority`, `category`, `assigned_to`, `due_date_from`, `due_date_to`, `overdue_only`). Computes dynamic `is_dependency_blocked` and `dependency_block_reasons`.
- `GET /api/v1/events/{event_id}/tasks/timeline` — Retrieve chronologically scheduled event timeline grouped by date, separating scheduled milestones/tasks from unscheduled backlog items.
- `GET /api/v1/events/{event_id}/tasks/progress` — Deterministic progress summary metrics (total tasks, counts by status, percentage completion, overdue counts, total estimated vs. actual costs).
- `GET /api/v1/events/{event_id}/tasks/activity` — Event-wide append-only chronological task activity audit trail.
- `GET /api/v1/events/{event_id}/tasks/{task_id}` — Retrieve task details with eager-loaded predecessor/successor dependencies and audit activity history.
- `PATCH /api/v1/events/{event_id}/tasks/{task_id}` — Partially update task attributes. Automatically validates dependency constraints across all 4 dependency types (`finish_to_start`, `start_to_start`, `finish_to_finish`, `start_to_finish`), maintains `completed_at` timestamps (clears on reopening), and records change events in the activity audit log. Never silently mutates user statuses.
- `DELETE /api/v1/events/{event_id}/tasks/{task_id}` — Soft delete task (`is_deleted=True`). Retains complete activity history for auditing and removes active dependency blocks.
- `POST /api/v1/events/{event_id}/tasks/{task_id}/dependencies` — Define dependency linking a predecessor to a successor task. Enforces same-event membership, prevents self-dependencies, rejects duplicate pairs, checks status constraints, and performs graph cycle detection using BFS.
- `DELETE /api/v1/events/{event_id}/tasks/{task_id}/dependencies/{dependency_id}` — Remove task dependency.
- `GET /api/v1/events/{event_id}/tasks/{task_id}/activity` — View append-only audit trail of task changes (status, priority, dates, assignments, creations, deletions). Remains 100% accessible even after task soft-deletion. Modifying or deleting activity entries is strictly disabled.

### AI Planning Intelligence Endpoints (`/api/v1/events/{event_id}/ai-advice` & `/api/v1/ai/event-advice`)
- `POST /api/v1/events/{event_id}/ai-advice` — Secure server-side Gemini planning advice grounded in authoritative backend event records and budget line items. Never relies on client-supplied financial totals. If API key is not configured, gracefully returns deterministic baseline guidance.
- `POST /api/v1/ai/event-advice` — Ad-hoc validated server-side Gemini event advice endpoint for interactive planning queries. Transmits keys strictly in server headers (`x-goog-api-key`), with bounded timeouts and sanitized error responses.

### GenAI Event Planning Assistant Endpoints (`/api/v1/assistant`)
- `GET /api/v1/assistant/status` — Reports planning assistant availability, configured Gemini model, and whether live GenAI planning or deterministic mode is active.
- `POST /api/v1/assistant/plan/generate` — Converts natural-language event descriptions into comprehensive, structured event plans (Event Brief, Personalized Ideas, Budget Proposal with deterministic Python financial calculation, Vendor Procurement Checklist, and Staged Timeline). Operates completely in-memory (draft preview) with zero unsolicited database writes.
- `POST /api/v1/assistant/plan/refine` — Refines an existing structured event plan based on user conversational adjustments (e.g., budget cuts, dietary switches, theme shifts, attendee changes) while recalculating financial totals with exact Python Decimal arithmetic.

---

## 🧪 Running Automated Tests

Run the complete test suite (Health, Database, Events, Vendors, Prices, Budgets, Tasks, Gemini AI, and Structured Planning Engine):

**From inside `backend/`:**
```powershell
pytest -v
```

**From repository root:**
```powershell
$env:PYTHONPATH="backend"
.\backend\.venv\Scripts\pytest backend/tests -v
```

---

## 🛡️ Security & Clean Boundaries
- All database credentials, secrets, API keys, and SQLite files (`*.db`, `*.sqlite`, `*.db-shm`, `*.db-wal`) are explicitly ignored in `.gitignore`.
- Gemini API key is configured **exclusively on the backend** and never exposed to the client or embedded in JavaScript bundles.
- Provider errors are sanitized so internal errors, stack traces, and API keys are never leaked to API callers.
- Database URL is fully switchable between SQLite and PostgreSQL through environment configuration without application code changes.
