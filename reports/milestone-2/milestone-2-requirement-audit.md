# BuildSure AI — Milestone 2 Requirement Audit

**Audit date:** 2026-11-04
**Scope:** Read-only repository inspection. The only deliverable from this task is this audit report. No source, model, dataset, test, or configuration files were changed. Tests were inspected but not run.

## Executive summary

The repository has a usable single-image PPE detection and risk-assessment foundation. The standard image endpoint maps explicit supported YOLO violation classes into normalized hazards, calculates project-defined risk values when exposure inputs are available, and can persist observations, detected hazards, and risk assessments when PostgreSQL is configured. A separate experimental endpoint returns raw detections, a Safety Agent alert proposal, and stateless LangGraph routing.

The complete mentor demo is **not implemented**. No code path currently inserts an Alert row, no alert list or status-update API exists, and no zone analytics endpoint or zone/worker dashboard exists. work_area is a nullable free-text field, not a project/site/zone model. The experimental endpoint explicitly makes no database writes and sends no notifications. Thus it can demonstrate a preview of detection → risk/finding → proposed alert/routing, but not violation → persisted alert lifecycle → zone-level analytics.

The current mapping supports explicit NO-Hardhat, NO-Mask, and NO-Safety Vest detections. The existing checkpoint has no NO-Gloves class; the project’s standard detector does not turn missing positive PPE detections into violations. Model quality and live deployment health were not re-evaluated in this read-only code audit.

## A. Requirement matrix

| Mentor requirement | Status | Repository evidence | What remains |
|---|---|---|---|
| 1. PPE detection operational | **Partially implemented** | The standard image route uses the dependency-provided YOLO detector, defaulting to the repository checkpoint when present; the detector preserves boxes and maps explicit supported violations. The experimental route separately loads weights/best.pt. See [detector.py](../../backend/app/detector.py), [main.py](../../backend/app/main.py), [safety_agent.py](../../backend/app/safety_agent.py), [README.md](../../README.md). | A functioning code path exists, but this audit did not execute it against a real site image or verify a running deployment. Current model evaluation documents weak class recall; runtime/operational readiness is not established. |
| 2. Safety alerts generated | **Partially implemented** | decide_alert creates an in-memory AlertDecision; the experimental response serializes alert_recommended, reason, and priority. Alert ORM schema exists. See [safety_agent.py](../../backend/app/safety_agent.py), [main.py](../../backend/app/main.py), [db_models.py](../../backend/app/db_models.py). | Neither image assessment route constructs/persists an ORM Alert nor sends a notification. Implement alert creation and delivery/dispatch semantics if actual alert generation is required. |
| 3. Worker safety analytics function | **Partially implemented** | OverviewCards calculates counts/average risk from the latest loaded observation page; observation history renders observed hazards and risk bands. See [OverviewCards.tsx](../../frontend/src/components/OverviewCards.tsx), [ObservationHistory.tsx](../../frontend/src/components/ObservationHistory.tsx). | These are observation/risk summaries, not worker-level analytics. No worker identity, tracking, worker aggregates, or analytics API exists. Add defined, privacy-reviewed analytics over persisted event data. |
| 4. Safety Agent and PPE event schema | **Partially implemented** | In-memory types separate raw Detection, DetectedHazard, HazardAssessment, recommendations, and AlertDecision. ORM/migration define Observation, DetectedHazardRecord, RiskAssessment, SafetyRecommendation, Alert, and AgentWorkflowRun. See [models.py](../../backend/app/models.py), [db_models.py](../../backend/app/db_models.py), [0001_initial_schema.py](../../alembic/versions/0001_initial_schema.py). | Existing schema is a good base, but there is no end-to-end persisted alert event pipeline or project/site/zone dimension. Clarify event identity, lifecycle, attribution, and retention before extending the schema. |
| 5. Helmet, vest, and other PPE checks | **Partially implemented** | Detector maps NO-Hardhat, NO-Mask, and NO-Safety Vest; compliant positive classes are filtered as non-hazards. The current model taxonomy contains positive Hardhat, Gloves, Mask, Safety Vest, Person and explicit missing classes for hardhat, mask, vest. See [detector.py](../../backend/app/detector.py), [risk_agent.py](../../backend/app/risk_agent.py), [PPE annotation policy](../model-evaluation/ppe-annotation-policy.md). | Current model has no NO-Gloves class and known evaluation recall is weak for multiple PPE classes. Do not infer a violation from a missing positive-class detection. Any proposed NO-Gloves support requires separate approved data/model work. |
| 6. Behavior and accident-prone-zone tracking | **Missing** | Repository inspection found no behavior recognition/tracking, temporal worker tracking, hazard-zone entity, or accident-prone-zone analysis. repeated_count is an externally supplied risk input, not tracked behavior. See [main.py](../../backend/app/main.py), [models.py](../../backend/app/models.py). | Define behavior/zone concepts and lawful data sources, then implement and validate them. A manually entered work_area does not satisfy this requirement. |
| 7. Violations linked to alerts and safety analytics | **Partially implemented** | ORM relationships connect Alert to Observation, DetectedHazardRecord, RiskAssessment, and SafetyRecommendation. The standard endpoint persists observations, hazards, and assessments. See [db_models.py](../../backend/app/db_models.py), [persistence.py](../../backend/app/persistence.py), [main.py](../../backend/app/main.py). | No alert persistence code or analytics query links those records into a usable alert/zone view. Complete the write path and read/query contracts. |
| 8. PPE violation event pipeline | **Partially implemented** | Standard path: image → detector hazard labels → SiteRiskAgent findings → optional score → observation/hazard/assessment persistence. Experimental path: raw YOLO detections → assess_safety → alert proposal → stateless graph routing. See [main.py](../../backend/app/main.py), [risk_agent.py](../../backend/app/risk_agent.py), [safety_agent.py](../../backend/app/safety_agent.py), [safety_graph.py](../../backend/app/safety_graph.py), [persistence.py](../../backend/app/persistence.py). | The paths are not one integrated event pipeline: the standard persisted path does not call the Safety Agent/graph or write recommendations/alerts; the experimental path does not persist. No alert lifecycle, idempotency or zone analytics follows the detection. |
| 9. Worker safety analytics view | **Partially implemented** | Dashboard has summary cards, upload results, and observation history; experimental viewer visualizes detections, findings, recommendations, alert proposal, and route decision. See [App.tsx](../../frontend/src/App.tsx), [OverviewCards.tsx](../../frontend/src/components/OverviewCards.tsx), [ExperimentalSafetyViewer.tsx](../../frontend/src/components/ExperimentalSafetyViewer.tsx). | There is no dedicated worker or zone safety analytics view, violation trend/common-type analysis, alert status view, or server-side aggregation. |
| 10. Alert history with status and timestamps | **Partially implemented** | Alert schema has alert_id, status (open, acknowledged, resolved, dismissed), created_at, acknowledged_at, resolved_at, plus optional source FKs. See [db_models.py](../../backend/app/db_models.py), [0001_initial_schema.py](../../alembic/versions/0001_initial_schema.py). | No route queries alerts, creates them, or updates status; no frontend history or resolve/acknowledge controls. Alert schema fields alone do not establish an alert history feature. |
| 11. Normal and unsafe sample cases | **Partially implemented** | Detector, risk, API, image-assessment, experimental endpoint, and graph tests use synthetic/fake detections; evaluation reports contain dataset examples and model evidence. See [backend/tests](../../backend/tests), [test evaluation report](../model-evaluation/outputs/test-evaluation-20261102T131609Z/evaluation_report.md), [validation analysis](../model-evaluation/outputs/validation-analysis-20261102T133016Z/validation_error_analysis.md). | No documented, human-approved application demo fixture set that exercises normal and unsafe cases through persistence, alert history, and zone analytics. Synthetic tests do not establish site accuracy. |
| Additional: mentor-required error case and recovery | **Partially implemented** | Input-size/type validation, controlled 400/413/422/503/409/500 responses, sanitized DB errors, transaction rollback, frontend errors/retry for history, and graph pending routing are present. Relevant tests include image assessment, experimental endpoint, observation API, persistence, and safety graph tests. | Recovery is primarily request retry/re-upload; no durable failed-event queue, retry policy, alert-delivery recovery, or operator-visible workflow-run history is wired. Demonstrate a failure and successful recovery through the eventual end-to-end workflow. |

## B. Existing architecture

### Standard persisted assessment path

1. POST /assessments/image receives one image and optional observation_id, free-text work_area, people count, duration, and repetition count.
2. get_hazard_detector() returns an explicitly configured mock, a YOLOv8 detector, or an unconfigured detector that raises an error. The YOLO adapter uses the checkpoint path from HAZARD_DETECTOR_WEIGHTS, otherwise the repository weights/best.pt when it exists. The YOLO adapter’s confidence default is 0.25.
3. normalize_detection_label() converts only explicit supported violation names to normalized labels. Positive PPE and ordinary objects are not findings. Person detections contribute to an exposure count.
4. SiteRiskAgent.detect_hazards() maps normalized labels to hazard types. assess_hazard() creates a project-rule score only when people count, duration, and repetition inputs are available; otherwise the detection can be returned as pending.
5. If a database session is configured, persist_observation_bundle() writes an Observation with DetectedHazardRecord and RiskAssessment records. Image bytes/overlay are separately saved for persisted image assessments.
6. The response returns detections/findings/assessments to the client. This path does not create alerts or invoke LangGraph.

### Experimental Safety Agent path

POST /experimental/safety/detect (with hidden alias /experimental/detect-safety) writes the upload to a temporary file, loads the Safety Agent’s checkpoint path, runs raw inference, builds supported hazards/recommendations, computes an alert proposal, and routes a state through LangGraph. It deletes the temporary file in finally. It explicitly does not write to PostgreSQL, update history, or send alerts. LangGraph only returns review-required, no-findings, or pending routing output; it does not call inference or create external side effects by itself.

### Frontend/backend boundary

The React app calls /health, /assessments/image, /observations, and the observation detail/image routes. The main dashboard shows upload results, summary cards over currently loaded observations, and recent history. The separate experimental tab calls the stateless experimental route and renders a preview. No frontend client method or FastAPI route for alerts or zone analytics was found. The frontend has no worker, site, or zone domain types beyond work_area: string.

## C. Data model gaps and reusable schema

Existing models should be reused and extended only after the event contract is clear:

- **Observation:** observation_id (string primary key), timestamp, source, free-text work_area, exposure inputs, confidence, raw metadata, and created/updated timestamps.
- **DetectedHazardRecord:** database-generated detected_hazard_id, observation FK, normalized hazard type/source label, confidence, detector metadata, evidence JSON, and detection time.
- **RiskAssessment:** per-detection version, pending/completed status, inputs, score/band, explanation, missing-input list, and assessment time.
- **SafetyRecommendation:** detected-hazard and optional assessment FKs, text, priority, status, and lifecycle timestamps.
- **Alert:** database-generated alert_id, observation FK, optional hazard/assessment/recommendation FKs, type/message/band, status, recipient, deduplication key, and created/acknowledged/resolved times.
- **AgentWorkflowRun:** workflow UUID, role, status, start/completion, input/output summaries, and error text.
- **In-memory/API contracts:** NormalizedObservation, DetectedHazard, HazardAssessment, persisted response models, and experimental response models.

A database-generated detected_hazard_id is a stable identifier once a hazard is persisted, and alert_id exists in the ORM. However, the in-memory hazard has no independent event ID; the experimental response returns no event ID; and neither ID currently participates in a live alert workflow. observation_id is client-supplied for JSON or generated as a short img-obs-<8 hex> token for image uploads. The latter is useful as a lookup key but is not a full event identity/duplicate policy.

The schema has no Project, Site, Zone, Worker, or WorkerTrack model. work_area is nullable free text on Observation. No migration or API contract associates an observation/hazard/alert with a normalized zone ID. AgentWorkflowRun exists in schema but no endpoint path invokes it or persists graph steps. Alert and recommendation schema status/timestamps do not provide application operations by themselves.

## D. Analytics gaps

No analytics endpoint or server-side aggregation was found. Current OverviewCards reports the number of observations loaded on the current page, high/critical scored assessments, pending scoring inputs, and average score. It does not mean total violations across the database; its history request is paginated (default 20).

| Desired analytic | Current evidence | Gap |
|---|---|---|
| Total violations | Counts hazards within observations currently loaded in UI; no explicit violation aggregate API. | Query persisted detection/hazard events across selected site and time window; define deduplication and whether repeated frames count separately. |
| Zone-wise counts / compare highest and lowest zones | work_area is displayed as a label for each observation. | Establish normalized site and zone IDs, then aggregate by zone/time period and support empty/unknown zones. |
| Common violation types | Hazard labels are displayed per observation. | Add aggregation/grouping by normalized hazard type with time and site filters. |
| Risk-level distribution | UI can count high/critical and display per-observation risk bands; assessments contain bands. | Add all-band aggregate and define treatment of unscored/pending records. |
| Unresolved alerts | No alert query/creation route; alert schema has statuses. | Persist alert lifecycle, then filter open/acknowledged records and define unresolved semantics. |
| Resolution status | ORM has alert/recommendation statuses and timestamps. | Add status transition endpoints, authorization/audit actor, lifecycle validation, and UI controls/history. |
| Worker safety analytics | No worker identity or tracking contract. | Define permitted worker-level aggregation and privacy controls before collecting identifiers or claiming worker-level metrics. |

## E. Demo gap analysis

### What is possible now

- Upload one image through the normal dashboard and return mapped hazard findings and optional project-rule risk scores.
- When PostgreSQL is configured, persist that observation and its detected hazards/assessments, then view recent observation history with source image and annotation overlay.
- Use the experimental viewer to show raw class/confidence/box information, supported findings, recommended actions, an alert proposal, and a LangGraph route decision.
- Demonstrate completed, no-supported-finding, and pending/incomplete graph outcomes using tests and mocked detections.

### What prevents the requested demo

There is no single request or workflow that runs inference, persists a violation event, creates an alert record, exposes that alert for officer review/resolution, and updates analytics for its zone. The standard persisted path and experimental proposal path are separate. There are no configured site/zone records or zone filters; free-text work area does not ensure consistent aggregation. Alert statuses are not writable or visible to users. Analytics cards summarize only a limited loaded page and omit zone comparisons and common violation counts.

### Error case and recovery

A defensible current failure demonstration is an invalid/corrupt/oversized image or unavailable model: API returns a controlled client/service error; the frontend exposes the error; the operator can correct/re-upload. For database persistence failure the API returns a sanitized 500 and database dependency rolls back the transaction. The graph protects against treating missing/invalid assessments as a clean no-finding outcome by routing them to assessment_pending. These are implemented guardrails, not a durable job recovery system. There is no saved failed event, workflow-run row, or alert delivery retry. A future demo should show a specific failure, visible failed/pending state, corrective action, successful retry, and resulting persisted event/alert/analytics state.

## F. Recommended implementation sequence

1. **Agree on event and tenancy contract.** Decide whether a project needs site and zone entities, how a work area maps to a zone, event/deduplication identity, and what total violations counts. Keep existing PPE class semantics intact.
2. **Connect the existing persisted records.** Extend the standard assessment transaction to persist evidence, recommendations, and an Alert for explicit supported violations, with stable relationships and idempotent deduplication. Preserve pending risk values rather than fabricating scores.
3. **Add alert operations.** Add paginated/filterable alert history and safe status transitions (acknowledge, resolve, dismiss) with timestamps and actor/audit evidence. Define authorization boundary for safety officer/management before exposing controls.
4. **Add analytics API.** Aggregate by selected project/site/zone and time window: total violations, zone rankings, common types, risk-band distribution, and unresolved alerts. Define treatment of unscored events and duplicate detections.
5. **Build the officer-facing view.** Add zone comparison, common violations, risk distribution, and an alert table/details/resolution flow backed only by those APIs.
6. **Add explicit workflow/error recovery.** Persist workflow-run state, define retries/idempotency and recovery after DB/model/notification failures, and expose useful status without claiming a failed notification was sent.
7. **Validate with focused tests and demo cases.** Cover normal/unsafe examples, persisted event-to-alert joins, multi-zone aggregation, status changes/timestamps, duplicate handling, invalid image/model/database/notification failures, and successful recovery. Keep a frozen evaluation set distinct from demo/training samples.

## G. Existing test baseline

The repository documents the standard backend command in [README.md](../../README.md):

    python -m unittest discover -s backend/tests -p "test_*.py"

Relevant existing test modules:

- [test_yolo_detector.py](../../backend/tests/test_yolo_detector.py): supported violation mapping, filtering, model load reuse, weight-load errors; uses fake model objects.
- [test_safety_file.py](../../backend/tests/test_safety_file.py): checkpoint path, parsing, hazard conversion, risk scoring, alert proposal.
- [test_risk_agent.py](../../backend/tests/test_risk_agent.py) and [test_api.py](../../backend/tests/test_api.py): normalized hazard/risk behavior and pending inputs with synthetic fixtures.
- [test_image_assessment.py](../../backend/tests/test_image_assessment.py): image endpoint, violation/no-violation, pending inputs, validation and error cases, image overlay; mostly mock detector.
- [test_persistence.py](../../backend/tests/test_persistence.py), [test_observation_api.py](../../backend/tests/test_observation_api.py), and [test_image_persistence.py](../../backend/tests/test_image_persistence.py): observation/hazard/assessment mapping, observation APIs, and image retention. They do not exercise alert persistence/status changes or analytics.
- [test_experimental_safety.py](../../backend/tests/test_experimental_safety.py): experimental preview response, alert proposal, routing, invalid input/model/inference errors, and verifies no database writes. Optional test calls real weights on a synthetic image if present; that is not representative model evaluation.
- [test_safety_graph.py](../../backend/tests/test_safety_graph.py): review/no-finding/pending routes and confirms graph has no persistence/notification side effects.
- [test_database_integration.py](../../backend/tests/test_database_integration.py): optional PostgreSQL migration and observation persistence checks when TEST_DATABASE_URL is set. README says this uses a disposable database; its teardown downgrades migrations, so do not point it at a valuable database.
- [frontend/package.json](../../frontend/package.json): scripts include build, lint, dev, and preview; there is no frontend test script configured.

Tests were not run for this audit. This report records the checked-in/current working-tree evidence only; a live database, production deployment, browser demo, notification provider, or deployed alert lifecycle was not independently verified.

## Scope and working-tree note

The audit did not edit implementation files or execute tests. Existing uncommitted work was left untouched. Git status already showed other tracked modifications and untracked files during inspection; this report does not claim those changes are part of this audit.
