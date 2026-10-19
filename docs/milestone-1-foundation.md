# Milestone 1 Foundation

## Current scope

Milestone 1 includes a small, rule-based Site Risk Agent, FastAPI assessment
and observation endpoints, local YOLO image-based hazard detection, PostgreSQL
persistence with Alembic migrations, and a React + TypeScript + Vite dashboard
with observation history.

The Construction-PPE dataset has not been downloaded or integrated, and no
real dataset is included in the repository. Unit-test fixtures remain
synthetic.

## Implemented deliverables

1. **Site Risk Agent** - implemented as a rule-based agent in
   `backend/app/risk_agent.py`.
2. **Site Monitoring Data** - normalized observations are accepted through the
   API and persisted to PostgreSQL when configured. Live sensor or stream
   integration remains future work.
3. **Hazard Detection** - supported PPE violations can be detected from local
   YOLO image inference and mapped through explicit rules. The Construction-PPE
   dataset itself is not integrated.
4. **Risk Scoring** - implemented using the project-defined formula and bands.
   Missing people, duration, or repetition inputs leave assessments pending
   rather than assigning a zero score.
5. **Dashboard** - implemented as a React + TypeScript + Vite dashboard with
   image upload, assessment results, status indicators, and observation
   history.

The current API exposes `GET /health`, `POST /assessments`,
`POST /assessments/image`, `GET /observations`, and
`GET /observations/{observation_id}`. PostgreSQL persistence is enabled through
`DATABASE_URL`; migrations are managed explicitly with Alembic and are not run
automatically during application startup.

## Project-defined risk scoring

The application calculates:

```text
risk_score = severity x likelihood x exposure
```

This is a project-defined educational formula. It is not an official OSHA
formula and must not be presented as a regulatory safety standard.

### Severity: 1-5

1. No injury expected.
2. Minor injury or first-aid case possible.
3. Medical treatment or recordable injury possible.
4. Serious injury, hospitalization, or permanent impairment possible.
5. Fatality, amputation, loss of an eye, or similarly severe outcome possible.

### Likelihood: 1-5

1. Rare or isolated.
2. Unlikely with limited exposure.
3. Occasional or recurring.
4. Frequent or repeatedly observed.
5. Persistent, very likely, or imminent.

In the current rule-based prototype, repeated observations are used as a
simple proxy for likelihood. This is not a statistical accident probability.

### Exposure: 1-4

1. One person or very brief exposure.
2. A few people or intermittent exposure.
3. Several people or repeated shift exposure.
4. Many workers, continuous exposure, or a high-traffic area.

### Project-defined score bands

| Score | Band | Project action |
|---:|---|---|
| 1-19 | Low | Monitor and record |
| 20-39 | Moderate | Correct during routine supervision |
| 40-69 | High | Take prompt corrective action |
| 70-100 | Critical | Escalate immediately and consider stopping the affected activity |

These bands are project conventions, not official safety thresholds.

## Detection confidence and likelihood

Detection confidence and accident likelihood are deliberately separate:

- Detection confidence is how certain the computer-vision model is about a
  label such as `no_helmet`.
- Likelihood is the project-defined judgement about how likely an incident is
  given repetition and site exposure.

A confidence of `0.91` does not mean a 91% accident probability.

## YOLO and dataset status

The local YOLO adapter supports the explicitly mapped violation classes
`NO-Hardhat`, `NO-Mask`, and `NO-Safety Vest`. Compliant PPE, people, vehicles,
and equipment are not returned as hazards; detected people can still provide
the exposure count.

Real inference requires the compatible Python 3.13 `.venv-yolo` environment and
local model weights. The lightweight `.venv` remains suitable for ordinary
backend tests without PyTorch or Ultralytics.

The preferred later visual dataset is the official
[Ultralytics Construction-PPE dataset](https://docs.ultralytics.com/datasets/detect/construction-ppe/).
It has not been downloaded or integrated in this milestone.

## Dataset licensing status

The Ultralytics page documents the Construction-PPE dataset and identifies an
AGPL-3.0 license. Before redistributing or integrating the dataset, verify the
exact license scope for images, annotations, attribution, redistribution, and
any trained weights. The dataset is therefore not included in this repository.

## Limitations

- YOLO inference is available locally with model weights; it is not a claim of
  production computer-vision accuracy.
- The current fixtures are synthetic and cannot support model-accuracy claims.
- The agent does not estimate real accident probabilities.
- The severity defaults are project assumptions that require mentor review.
- The system does not replace a safety professional or site inspection.
- Live monitoring streams, authentication, production deployment, and external
  integrations are not implemented.

## Planned orchestration work

LangGraph and four-agent orchestration are not implemented in the current code.
The current application uses one rule-based Site Risk Agent. The database
workflow-run role values provide schema support for future workflows; they do
not represent active orchestration.

Potential future roles are Hazard Detection, Risk Assessment, Safety Response,
and Reporting & Alerts, subject to confirmation of the final architecture.
