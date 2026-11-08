# agentic-construction-risk-analytics
Agentic Construction Risk Intelligence Platform

## Current status

The repository contains the SafeSite Risk Intelligence local application: a
FastAPI backend, real-checkpoint YOLO image analysis, PostgreSQL persistence,
Alembic migrations, authentication, and a React + TypeScript + Vite dashboard
with observation history, alerts, and work-area analytics. Risk decisions use a
provisional educational policy; an empty result is not proof of site safety.

The trained model weights and datasets remain local and are not committed. The
standard `.venv` supports lightweight backend tests, while `.venv-yolo` is used
for local Ultralytics inference.

See [docs/milestone-1-foundation.md](docs/milestone-1-foundation.md) for the
scoring formula, limitations, dataset status.

## Normal local application

Use the clean local PostgreSQL database `safesite_local`. It was migrated to
repository head `0003_alert_dismissed_at` and began with zero observations,
detected hazards, risk assessments, and alerts. Normal startup and local account
bootstrap explicitly target this database; they do not modify the root `.env`
or the preserved `safesite_demo` database.

See [SafeSite local application setup](docs/local-setup.md) for prerequisites,
database creation/migration, private bootstrap configuration, and the full
startup procedure. From the repository root, once setup is complete:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\start_local_backend.ps1'
```

In a second terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open `http://localhost:5173/#login`. Sign in with a local account documented in
the setup guide. Normal screens begin empty; safety records and analytics come
from images and assessments actually submitted through the application.

The prepared `safesite_demo` database and its separate accounts remain intact
as an optional [mentor walkthrough fallback](docs/local-mentor-demo.md).

## Backend-only development

The standard backend environment can run the rule-based agent and mock detector
without ML dependencies. Real YOLO inference is available locally through the
Python 3.13 `.venv-yolo` environment and the configured model weights.

From the repository root, create or activate the Python 3.14 virtual
environment, then install the runtime dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

To install the additional test dependency:

```powershell
python -m pip install -r requirements-dev.txt
```

For backend-only development, Uvicorn can also be started directly. This uses
the current `DATABASE_URL` rather than selecting `safesite_local`, so use the
normal local startup command above for the connected application:

```powershell
python -m uvicorn backend.app.main:app --reload
```

The API provides:

- `GET /health` — checks that the backend is running.
- `POST /assessments` — accepts one normalized observation and returns the
  supported hazard assessments.

The API also provides:

- `POST /assessments/image` for configured image hazard detection and risk
  assessment.
- `GET /observations` for saved observations when PostgreSQL is configured.
- `GET /observations/{observation_id}` for one saved observation and its
  detected hazards and assessments.

FastAPI also provides interactive documentation at
`http://127.0.0.1:8000/docs` while the server is running.

Run all tests from the repository root with:

```powershell
python -m unittest discover -s backend/tests -p "test_*.py"
```

## Run real YOLO image inference locally

The original `.venv` is intentionally kept free of PyTorch and Ultralytics.
For local YOLO inference, use the Python 3.13 `.venv-yolo` environment. Install
the backend and optional ML dependencies into that environment only if they are
not already present:

```powershell
.\.venv-yolo\Scripts\python.exe -m pip install -r requirements-ml.txt
```

Keep `weights/best.pt` local; it is excluded by `.gitignore`. Configure its
path in the same PowerShell session before starting the API:

```powershell
$env:HAZARD_DETECTOR_WEIGHTS = (Resolve-Path .\weights\best.pt).Path
Remove-Item Env:HAZARD_DETECTOR_MODE -ErrorAction SilentlyContinue
.\.venv-yolo\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

This older backend-only startup can be run through:

```powershell
.\scripts\start_backend_yolo.ps1
```

This script selects `.venv-yolo` and resolves the local checkpoint, but it does
not explicitly select `safesite_local`. Use `start_local_backend.ps1` for the
normal application.

The model maps `NO-Hardhat`, `NO-Mask`, and `NO-Safety Vest` to the existing
hazard labels. Compliant PPE, people, vehicles, and equipment are filtered
from the hazard list; detected people are still used as the exposure count.
The existing response contract is preserved, and assessments remain pending
when required duration or repetition inputs are missing.

## PostgreSQL configuration

The project uses SQLAlchemy with Psycopg 3 for PostgreSQL connectivity. ORM
models and an initial Alembic migration define the application persistence
schema. The API uses `DATABASE_URL` when configured and remains stateless for
ordinary tests when it is absent. Migrations are explicit and are not run
automatically at application startup.

Set `DATABASE_URL` in the local environment without committing credentials:

```text
postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME
```

For the normal local application, the database name is `safesite_local`. Keep
the real PostgreSQL connection password in a local `.env` file or environment
setting excluded by `.gitignore`; the normal local scripts reuse that local
server connection while explicitly selecting `safesite_local`. They do not
rewrite `.env`.

Database migrations are managed with Alembic and are not run automatically when
the FastAPI application starts. For `safesite_local`, use the explicit verified
migration command from the [local setup guide](docs/local-setup.md). For other
intentionally selected databases, inspect or apply migrations from the root:

```powershell
python -m alembic current
python -m alembic upgrade head
```

The optional PostgreSQL integration test uses `TEST_DATABASE_URL` and should
point to a disposable test database. Without that variable, it is skipped:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@localhost:5432/construction_risk_test_db"
python -m unittest discover -s backend/tests -p "test_*.py"
```

## Limitations and planned work

The current YOLO integration supports only the explicitly mapped PPE violation
classes (`NO-Hardhat`, `NO-Mask`, and `NO-Safety Vest`). The supplementary
Construction-PPE dataset has been downloaded and inspected but has not been
integrated; the application fixtures remain synthetic and do not support
model-accuracy claims.

The dataset has **not** been merged into the existing dataset or used for
retraining. See the [Milestone 2 progress log](docs/milestone-2-progress-log.md)
and the dataset evaluation reports for the current blockers and evidence.

The project-defined formula is educational and is not an OSHA calculation or
regulatory safety standard. The system does not estimate real accident
probabilities and does not replace a safety professional or site inspection.

The standard observation assessment uses a rule-based Site Risk Agent. An
experimental image path also uses a Safety Agent with conditional LangGraph
routing. Live monitoring streams, production deployment, and external
notification delivery remain planned work.

## Milestone 2 progress

See the [Safety Intelligence & Worker Protection progress log](docs/milestone-2-progress-log.md)
for verified implementation status, evaluation evidence, current blockers, and
next steps. Dataset integration and training remain blocked pending rights,
annotation, split-integrity, and human-approval gates.

## Fresh Windows environment

Install Git, local PostgreSQL, Node.js compatible with Vite 8 (22.12+ or 24+),
and Python. This checkout uses Python 3.13 for YOLO and Python 3.14 for
lightweight tests. From the repository root, create environments only if absent:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
py -3.13 -m venv .venv-yolo
.\.venv-yolo\Scripts\python.exe -m pip install -r requirements-ml.txt
cd frontend
npm.cmd ci
cd ..
```

Obtain the existing approved `weights/best.pt` separately; weights and datasets
remain local. Copy `.env.example` to `.env` only if `.env` does not exist.
Privately fill the PostgreSQL connection and three `SAFESITE_LOCAL_*_PASSWORD`
settings. Never commit `.env`. Existing installations retain current passwords;
bootstrap refuses conflicts. Demo variables are only needed for demo bootstrap.
Normal startup generates a temporary JWT secret; restarts require signing in.

Create `safesite_local` in PostgreSQL administration only if absent, granting
your configured local database user migration rights. Never drop existing data.
Then run from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate_local_database.ps1
.\.venv-yolo\Scripts\python.exe -m backend.app.bootstrap_local_accounts
```

Normal backend startup:

```powershell
cd "C:\Users\ALL AtoZ\OneDrive\Documents\GitHub\agentic-construction-risk-analytics"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_backend.ps1
```

In another terminal from the project root:

```powershell
cd frontend
npm.cmd run dev
```

Backend: `http://127.0.0.1:8000`; health:
`http://127.0.0.1:8000/health`; frontend: `http://localhost:5173`.
Vite may select 5174 or another port when 5173 is occupied; use its printed URL.

## Ports and stopping servers

Press **Ctrl+C** in each server terminal. For a port conflict, inspect the owner:

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,OwningProcess
Get-Process -Id <OwningProcess>
```

Prefer the original terminal. If needed, `Stop-Process -Id <verified-server-id>`
can stop a confirmed application server. Do not stop PostgreSQL or unrelated
services. The frontend proxy expects backend port 8000. If activation is blocked,
invoke the environment Python directly as shown above.

## Modules and checks

Overview summarizes persisted findings. AI Safety Analysis runs still-image PPE
inference and saves observations/evidence. Safety Incidents provides history,
manual work-area editing and authorized pending-assessment completion. The shared
decision engine distinguishes pending, no-alert, warning and alert states.
Alert Register supports acknowledgement, resolution and dismissal. Zone Analytics
groups hazard rows by work area; Recurrence Analytics counts distinct historical
observations. Reports supports filters and PDF export. Authentication enforces
Admin, Safety Officer and regular-user permissions in the backend.

FastAPI, SQLAlchemy/Psycopg and Alembic provide backend/PostgreSQL persistence.
React, TypeScript, Vite and Tailwind provide the frontend. YOLO/Ultralytics and
PyTorch provide inference; LangGraph supports experimental Safety Agent routing.
See the [baseline record](docs/milestone-2-baseline.md).

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py"
cd frontend
npm.cmd run build
npm.cmd run lint
```

Build includes TypeScript checking. Leave `TEST_DATABASE_URL` unset for ordinary
unit tests. PostgreSQL integration tests migrate and tear down their target;
use a separate disposable test database, never `safesite_local` or
`safesite_demo`. There is no frontend component test harness.

Detection supports still images and limited explicit PPE classes, with recall
gaps. Human review and operator context remain necessary. Free-text work areas
are not authoritative site identities. Recurrence is informational. Scoring and
alert thresholds remain provisional educational policy. No live video, external
notification delivery, accident prediction or safety certification is provided.

The existing `.venv` may need its declared dependencies refreshed. The full suite
can also run with `.\.venv-yolo\Scripts\python.exe` after installing `requirements-dev.txt` there.
