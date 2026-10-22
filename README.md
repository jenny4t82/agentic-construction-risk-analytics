# agentic-construction-risk-analytics
Agentic Construction Risk Intelligence Platform

## Current status

The repository contains the Milestone 1 backend and dashboard foundation. It
includes a rule-based Site Risk Agent, project-defined risk scoring, pending
assessments for incomplete inputs, FastAPI endpoints, optional local YOLO image
inference, PostgreSQL persistence, Alembic migrations, and a React + TypeScript +
Vite dashboard with observation history.

The trained model weights and datasets remain local and are not committed. The
standard `.venv` supports lightweight backend tests, while `.venv-yolo` is used
for local Ultralytics inference.

See [docs/milestone-1-foundation.md](docs/milestone-1-foundation.md) for the
scoring formula, limitations, dataset status.

## Run the FastAPI backend

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

Start the local API with Uvicorn:

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

For the local database, the database name is `construction_risk_db`. Keep the
real password in a local `.env` file or environment setting excluded by
`.gitignore`; do not place it in source code or documentation.

Database migrations are managed with Alembic and are not run automatically when
the FastAPI application starts. With `DATABASE_URL` set, inspect or apply the
migrations from the repository root:

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
classes (`NO-Hardhat`, `NO-Mask`, and `NO-Safety Vest`). The Construction-PPE
dataset has not been downloaded or integrated, and the current fixtures are
synthetic; they do not support model-accuracy claims.

The project-defined formula is educational and is not an OSHA calculation or
regulatory safety standard. The system does not estimate real accident
probabilities and does not replace a safety professional or site inspection.

The current application uses one rule-based Site Risk Agent. Live monitoring streams,
authentication, production deployment, and external integrations remain
planned work.
