# Milestone 1 Backend Foundation

## Current scope

This first implementation is a small, rule-based Site Risk Agent. It uses
synthetic test fixtures only. No real construction-site records or downloaded
datasets are included yet.

The preferred later visual dataset is the official
[Ultralytics Construction-PPE dataset](https://docs.ultralytics.com/datasets/detect/construction-ppe/).
It is intentionally not downloaded or integrated in this milestone step.

## Project-defined risk scoring

The application calculates:

```text
risk_score = severity × likelihood × exposure
```

This is a project-defined educational formula. It is not an official OSHA
formula and must not be presented as a regulatory safety standard.

### Severity: 1–5

1. No injury expected.
2. Minor injury or first-aid case possible.
3. Medical treatment or recordable injury possible.
4. Serious injury, hospitalization, or permanent impairment possible.
5. Fatality, amputation, loss of an eye, or similarly severe outcome possible.

### Likelihood: 1–5

1. Rare or isolated.
2. Unlikely with limited exposure.
3. Occasional or recurring.
4. Frequent or repeatedly observed.
5. Persistent, very likely, or imminent.

In the current rule-based prototype, repeated observations are used as a
simple proxy for likelihood. This is not a statistical accident probability.

### Exposure: 1–4

1. One person or very brief exposure.
2. A few people or intermittent exposure.
3. Several people or repeated shift exposure.
4. Many workers, continuous exposure, or a high-traffic area.

### Project-defined score bands

| Score | Band | Project action |
|---:|---|---|
| 1–19 | Low | Monitor and record |
| 20–39 | Moderate | Correct during routine supervision |
| 40–69 | High | Take prompt corrective action |
| 70–100 | Critical | Escalate immediately and consider stopping the affected activity |

## Detection confidence and likelihood

Detection confidence and accident likelihood are deliberately separate:

- Detection confidence is how certain a future computer-vision model is about
  a label such as `no_helmet`.
- Likelihood is the project-defined judgement about how likely an incident is
  given repetition and site exposure.

A confidence of `0.91` does not mean a 91% accident probability.

## Five Milestone 1 deliverables

1. **Site Risk Agent** — implemented as `backend/app/risk_agent.py`.
2. **Site Monitoring Data** — the normalized observation model is implemented;
   real dataset integration remains future work.
3. **Hazard Detection** — supported labels such as `no_helmet` are mapped to
   named hazards by explicit rules.
4. **Risk Scoring** — implemented and tested using the project-defined formula
   and bands.
5. **Dashboard** — not started; it will consume a future FastAPI API and show
   the agent's assessments.

Only the first four foundations have code at this stage. The five deliverables
must not be reported as complete until the real data integration and dashboard
are implemented and tested.

## Dataset licensing status

The Ultralytics page documents the Construction-PPE dataset and identifies an
AGPL-3.0 license. Before submission, we still need to verify the exact license
scope for images, annotations, redistribution, attribution, and any trained
weights. The dataset is therefore not included in this repository.

## Limitations

- The agent does not perform YOLO inference.
- It does not estimate real accident probabilities.
- It does not replace a safety professional or site inspection.
- The severity defaults are project assumptions that require mentor review.
- The current fixtures are synthetic and cannot support accuracy claims.
