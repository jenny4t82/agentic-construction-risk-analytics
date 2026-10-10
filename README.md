# agentic-construction-risk-analytics
Agentic Construction Risk Intelligence Platform

## Current status

The repository currently contains the initial backend foundation for Milestone
1. It includes a rule-based Site Risk Agent, normalized observations,
project-defined risk scoring, and automated tests using synthetic fixtures.

No real dataset, YOLO model, frontend, database, or external API has been
integrated yet.

See [docs/milestone-1-foundation.md](docs/milestone-1-foundation.md) for the
scoring formula, limitations, dataset status, and the planned relationship to
the five Milestone 1 deliverables.

## Run the FastAPI backend

The backend currently uses synthetic observations and the existing rule-based
Site Risk Agent. It does not download datasets or perform YOLO inference.

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

FastAPI also provides interactive documentation at
`http://127.0.0.1:8000/docs` while the server is running.

Run all tests from the repository root with:

```powershell
python -m unittest discover -s backend/tests -p "test_*.py"
```
