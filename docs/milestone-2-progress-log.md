# Milestone 2 Progress Log - Safety Intelligence & Worker Protection

## Current snapshot

- **Current milestone:** Safety Intelligence & Worker Protection (mentor-defined Weeks 3-4).
- **Current phase:** Phase 8.1A assessment queries, safe context correction, audit and alert reconciliation implemented on `revamp/milestone-2`; see the [API contract](phase-8-1a-assessment-contracts.md). Phase 8 baseline remains preserved. No local/demo data, model weights or scoring policy changed.
- **Overall status:** In progress. Local prototype and evaluation evidence exist; construction-safety readiness and required end-to-end deliverables remain incomplete.
- **Last updated:** 2026-11-09.
- **Current blockers:** Supplementary image/photo rights and license scope; scene-family overlap across supplementary train and the frozen existing test set; ten orphan label pairings; `no_gloves` task/policy semantics; human approval of any future class map and split plan; source access/codebooks for candidate datasets.
- **Next planned task:** Review the Phase 8.1A contracts and verification limits, then issue Antigravity a separate UI task. Disposable PostgreSQL concurrency and connected-browser checks remain outstanding; visual redesign has not started. Policy/model review remains separate.

This log records implementation evidence, not aspirations. A mentioned feature is not marked complete without repository evidence. No separate mentor slide deck or Milestone 2 requirements document was found in the repository search; the expectations below are transcribed from the project brief supplied for this phase.

## Milestone objectives and requirement tracking

Status vocabulary is used exactly as requested: `Not started`, `In progress`, `Implemented`, `Tested`, `Blocked`. `Tested` is used only where an executed evaluation or test artifact provides evidence. None of these statuses implies a certified or production-ready safety system.

| Requirement | Mentor expectation | Current implementation | Evidence | Status | Remaining work | Risks or limitations |
|---|---|---|---|---|---|---|
| PPE detection operational | PPE detection operational | Local YOLOv8n checkpoint and image-inference path; explicit violation mappings. | [`safety_agent.py`](../backend/app/safety_agent.py), [`detector.py`](../backend/app/detector.py), [`test-evaluation-20261102T131609Z`](../reports/model-evaluation/outputs/test-evaluation-20261102T131609Z/evaluation_report.md) | In progress | Improve and validate model against representative, rights-cleared data; verify runtime reliability and target-site conditions. | Test-set recall is limited; the evaluation is a dataset baseline, not an operational guarantee. |
| Safety alerts generated | Safety alerts generated | The shared provisional decision gates new actionable alert rows: alert-grade findings in an overall `alert` observation create rows; warning/pending/no-alert findings do not. Observation/hazard/assessment and decision metadata remain queryable. | [`decision_engine.py`](../backend/app/decision_engine.py); [`persistence.py`](../backend/app/persistence.py); [`test_alert_policy_persistence.py`](../backend/tests/test_alert_policy_persistence.py); Phase 5B-2 connected verification below | Tested | Obtain mentor policy approval. | Historical alert rows remain unchanged and may reflect the earlier create-for-every-violation behavior; no notification delivery exists. |
| Pending risk assessment completion | Safety Officer/Admin can finish an incomplete persisted PPE assessment | `PATCH /assessments/{assessment_id}/complete` fills only missing observation context, scores the existing assessment through `SiteRiskAgent`, reruns the shared decision, and creates only policy-actionable alerts. Observation History and the primary AI Safety Analysis result expose the form to manager roles. | [`persistence.py`](../backend/app/persistence.py), [`main.py`](../backend/app/main.py), [`ObservationHistory.tsx`](../frontend/src/components/ObservationHistory.tsx), [`App.tsx`](../frontend/src/App.tsx); Phase 6B/6C verification below | Tested | Prepare repeatable mentor-demo use with operator-managed credentials. | No arbitrary correction of completed assessments; no notification delivery or mentor-approved threshold. |
| Worker safety analytics functional | Worker safety analytics functional | Backend `/analytics/zones` retains hazard-row metrics; read-only `/analytics/work-area-recurrence` counts distinct observations per named work area and canonical supported PPE violation. Separate frontend Zone Analytics and Recurrence Analytics pages consume those endpoints. | [`analytics.py`](../backend/app/analytics.py), [`test_recurrence_analytics.py`](../backend/tests/test_recurrence_analytics.py), [`ZoneAnalyticsPage.tsx`](../frontend/src/components/ZoneAnalyticsPage.tsx), [`RecurrenceAnalyticsPage.tsx`](../frontend/src/components/RecurrenceAnalyticsPage.tsx); Phase 6D connected verification below | Tested | Refine observation drill-down and establish first-class location identity in a later phase. | `work_area` is nullable free text, not a validated zone entity; recurrence is observational, not worker-specific. |
| Safety Agent and PPE event schema | Safety Agent and PPE event schema | Safety Agent separates raw detections, supported hazards, scoring, recommendation, and alert proposal; ORM models include observations, detected hazards, assessments, recommendations, alerts, and workflow runs. | [`safety_agent.py`](../backend/app/safety_agent.py), [`db_models.py`](../backend/app/db_models.py), [`models.py`](../backend/app/models.py) | Implemented | Validate schema against mentor event requirements and decide how evidence/lineage is retained. | Declared schema relationships do not prove every workflow is active or persisted. |
| Helmet, vest, and other PPE checks | Helmet, vest, and other PPE checks | Existing model has positive and explicit missing-PPE classes; Safety Agent only creates findings from supported explicit violation labels. | [`detector.py`](../backend/app/detector.py), [`safety_agent.py`](../backend/app/safety_agent.py), held-out metrics report | In progress | Improve weak classes and verify annotation consistency; preserve explicit-violation semantics. | No absence-of-positive-PPE inference. Current 25-class model has no `NO-Gloves` class. |
| Behavior and accident-prone zone analysis | Behavior and accident-prone zone analysis | Phase 4 reports repeated PPE-violation observations and hazard-heavy named work areas as informational history only. No behavior recognition, accident outcomes or accident-probability model exists. | [`analytics.py`](../backend/app/analytics.py), [`test_recurrence_analytics.py`](../backend/tests/test_recurrence_analytics.py) | In progress | Define and validate Site/Zone/Inspection identity and any future outcome data before broader claims. | Free-text `work_area` cannot establish an accident-prone zone or worker behavior. |
| Violations linked to alerts and analytics | Violations linked to alerts and analytics | All supported findings persist with assessment/evidence lineage; only policy-actionable findings receive new alert rows. Image hazards now use the maximum confidence among detections mapping to their own canonical type and retain matching boxes in hazard evidence. Zone analytics derive violation totals from persisted hazards, not alert rows. | [`main.py`](../backend/app/main.py), [`persistence.py`](../backend/app/persistence.py), [`test_database_integration.py`](../backend/tests/test_database_integration.py); Phase 6A verification below | Tested | Keep model and evidence quality under review. | Older observations may retain incorrectly attributed confidence and are not rewritten; experimental route remains stateless. |
| Alert history with statuses and timestamps | Alert history with statuses and timestamps | Authenticated alert list/detail endpoints expose persisted lineage and nullable acknowledgment/resolution/dismissal timestamps; Safety Officer/Admin-only lifecycle endpoints support forward-only transitions. The preserved demo database reached `0003_alert_dismissed_at` in Phase 6B. | [`db_models.py`](../backend/app/db_models.py), [`main.py`](../backend/app/main.py), [`persistence.py`](../backend/app/persistence.py), [`0003_alert_dismissed_at.py`](../alembic/versions/0003_alert_dismissed_at.py); Phase 6A/6B verification below | Tested | Apply current migration head to any other older database before use. | Historical dismissed alerts have null `dismissed_at`; no external notification delivery. |
| Normal and unsafe sample cases | Normal and unsafe sample cases | Dataset splits and validation examples include compliant/violation classes; model evaluation has predictions and GT visual evidence. | [`test-evaluation-20261102T131609Z`](../reports/model-evaluation/outputs/test-evaluation-20261102T131609Z/evaluation_report.md), validation analysis | In progress | Prepare approved reproducible normal/unsafe application-level demo cases and document expected behavior. | Public dataset and class policy limitations may not represent the project's target sites. |
| PPE violation -> alert -> zone-level analytics demo | Demonstrate PPE violation -> alert -> zone-level analytics | Backend persistence links alert-grade findings to actionable alerts; warnings/pending remain in persisted history, and `/analytics/zones` aggregates supported findings by temporary `work_area`. The frontend distinguishes all four backend outcomes. | [`persistence.py`](../backend/app/persistence.py), [`analytics.py`](../backend/app/analytics.py), [`SafetyDecisionPanel.tsx`](../frontend/src/components/SafetyDecisionPanel.tsx); Phase 5B-2 connected verification below | Tested | Prepare an operator-run demo using vetted samples and controlled test inputs. | No delivered notification or validated zone entity exists; frontend recurrence view is still pending. |
| Explain input, processing, and output | Explain input, processing, and output | README and safety-graph documentation explain model and workflow paths. | [`README.md`](../README.md), [`safety-graph.md`](./safety-graph.md) | In progress | Prepare a milestone presentation/script with clear example input, evidence, processing, and output. | No separate mentor presentation file was found. |
| Include an error/recovery case | Include an error/recovery case | Graph distinguishes completed findings, completed no-finding, and incomplete/invalid assessment; tests pass in the backend suite. | [`safety_graph.py`](../backend/app/safety_graph.py), [`test_safety_graph.py`](../backend/tests/test_safety_graph.py) | Tested | Demonstrate a reproducible error/recovery case in the mentor demo. | Passing tests do not replace an operational recovery drill. |
| Trace data lineage | Trace data lineage | Evaluation reports include checkpoint/dataset hashes; supplementary dataset has a provenance record and manifest proposal. | [`ultralytics-dataset-provenance.json`](../reports/model-evaluation/ultralytics-dataset-provenance.json), evaluation report | In progress | Extend lineage to image/source/annotation decisions and runtime evidence retention. | Supplementary per-image photo sources and rights are unresolved. |
| Log decisions and retain appropriate evidence | Log decisions and retain appropriate evidence | Standard persistence now records overall decision metadata on observations and per-finding decisions alongside hazard evidence, with linked assessment and alert lineage when actionable. | [`persistence.py`](../backend/app/persistence.py), [`db_models.py`](../backend/app/db_models.py), [`test_alert_policy_persistence.py`](../backend/tests/test_alert_policy_persistence.py) | Tested | Verify live DB retention/query behavior and define policy-controlled retention. | Experimental route is stateless; privacy/retention policy not documented. |
| Explain risk scores | Explain risk scores | Project-defined severity/likelihood/exposure formula and per-assessment explanation are implemented. | [`risk_agent.py`](../backend/app/risk_agent.py), [`milestone-1-foundation.md`](./milestone-1-foundation.md) | Implemented | Continue labeling scores as educational project heuristics. | Not a statistical accident probability or regulatory formula. |
| Evaluate false positives, false negatives, and outages | Evaluate false positives, false negatives, and outages | Held-out test evaluation and validation-only threshold/error analysis quantify model errors. | [`test-evaluation-20261102T131609Z`](../reports/model-evaluation/outputs/test-evaluation-20261102T131609Z/evaluation_report.md), [`validation-analysis-20261102T133016Z`](../reports/model-evaluation/outputs/validation-analysis-20261102T133016Z/validation_error_analysis.md) | In progress | Add service/outage and recovery evaluation; retain false-positive/negative review and repeat after approved model changes. | Test metrics do not establish deployment reliability or generalization. |
| Maintain human oversight | Maintain human oversight | Alert proposals and review routing are explicit; authenticated Safety Officer/Admin roles are required for alert lifecycle changes; dataset-review findings still require human decisions. | [`safety_agent.py`](../backend/app/safety_agent.py), [`auth.py`](../backend/app/auth.py), [`safety_graph.py`](../backend/app/safety_graph.py), [`test_auth.py`](../backend/tests/test_auth.py) | In progress | Complete operational review procedures before use. | Role checks do not replace professional site inspection. |
| Respect privacy | Respect privacy | Experimental route uses temporary upload and documents no DB write/notification; ordinary observations can persist in PostgreSQL. | [`main.py`](../backend/app/main.py), [`ExperimentalSafetyViewer.tsx`](../frontend/src/components/ExperimentalSafetyViewer.tsx) | In progress | Document consent, retention/deletion, access control, worker-image handling, and applicable privacy review. | Temporary handling on one route does not establish platform-wide privacy controls. |
| Avoid claims that alerts prevent accidents | Do not claim alarms prevent accidents | Documentation says the system is educational and not a substitute for a safety professional/site inspection. | [`milestone-1-foundation.md`](./milestone-1-foundation.md), [`README.md`](../README.md) | Implemented | Preserve caveats in demos and future product language. | No evidence supports accident-prevention claims. |

## Verified model-evaluation baseline

The current baseline evaluation used 82 held-out test images with 806 labeled instances. It reported precision **0.6654**, recall **0.3660**, mAP50 **0.4264**, and mAP50-95 **0.2778**. This is a dataset-level baseline, not a real-world safety guarantee. Validation-only analysis used 114 images and 733 ground-truth instances with class-aware one-to-one matching at IoU >= 0.50. It showed a precision/recall trade-off across confidence thresholds; no production threshold was changed or selected from the held-out test set.

The training notebook's earlier validation metrics were precision 0.463, recall 0.458, mAP50 0.435, and mAP50-95 0.288. These are from a different split/protocol and are descriptive rather than a controlled before/after comparison.

## Dataset research and inspection evidence

- Official Ultralytics Construction-PPE was downloaded to `datasets/external/ultralytics-construction-ppe/` and inspected separately from the existing evaluation dataset.
- It contains 1,416 images (1,132 train, 143 validation, 141 test) and 11,521 image-matched annotation rows. Ten additional orphan training labels contain 93 rows.
- Archive SHA256: `BEF8DCB599AA4E9D9F5E602CB6FA7143D3C84D7F6A0FF40463D7F2A4C2632CCC`.
- Initial comparison identified 13 near-duplicate scene candidates; visual review confirmed scene-family overlap, including nine supplementary-training pairs near the existing held-out test scene.
- Six `no_gloves` samples (two per split) were reviewed; all six were outside construction contexts. This limits the class's immediate SafeSite suitability but does not establish that every source annotation is wrong.
- Dataset-level AGPL declaration, Ultralytics software licensing, and underlying photo rights are separate issues. Underlying photo provenance/redistribution permission is unresolved.
- Phase 2B review and Phase 2C planning are documented below; the supplementary dataset remains unmerged and training remains blocked.
- Phase 2D Stage 1 audited all eight project PPE policy classes against the unchanged 25-class model, application mappings, and matched source annotations. The original dataset has no `NO-Gloves`; the supplementary set has `no_gloves`, but the six prior visual concerns remain documented and the current representative sample also includes out-of-scope contexts. The supplement has no direct `no_mask` or `no_vest` classes. No annotations, YAMLs, application code, or model files were changed.

Detailed records: [evaluation](../reports/model-evaluation/outputs/test-evaluation-20261102T131609Z/evaluation_report.md), [validation analysis](../reports/model-evaluation/outputs/validation-analysis-20261102T133016Z/validation_error_analysis.md), [dataset inspection](../reports/model-evaluation/ultralytics-dataset-inspection.md), [dataset integration readiness](../reports/model-evaluation/dataset-integration-readiness.md), [licensing review](../reports/model-evaluation/licensing-review.md), [Phase 2C plan](../reports/model-evaluation/phase-2c-integration-plan.md), [Phase 2D annotation policy](../reports/model-evaluation/ppe-annotation-policy.md), [gap analysis](../reports/model-evaluation/ppe-remediation-gap-analysis.md), [Stage 1 decisions](../reports/model-evaluation/ppe-stage-1-decisions.md), [audit CSVs and contact sheets](../reports/model-evaluation/outputs/ppe-audit/).

## Backend authentication and role policy

- Migration `0002_user_accounts` adds persisted accounts with unique normalized email, scrypt password hash, `is_active`, and constrained roles (`user`, `safety_officer`, `admin`). Public signup can create only `user`; login returns a one-hour HS256 bearer JWT signed with `SAFESITE_JWT_SECRET` (minimum 32 UTF-8 bytes). The token identifies the account; each protected request loads the current role and active flag from the database.
- Apply migrations before use: `alembic upgrade head`. Set `DATABASE_URL` and `SAFESITE_JWT_SECRET` in the server environment. Create the first Admin through the operator-only hidden-password prompt: `python -m backend.app.bootstrap_admin`. There is no public Admin signup. An existing Admin can then assign Safety Officer/Admin roles through `PATCH /auth/users/{user_id}/role`.
- `GET /health`, signup, and login are public. All safety, observation, alert-read, analytics, and experimental routes require an authenticated account. Alert creation and lifecycle changes require Safety Officer or Admin; role changes require Admin. The existing experimental route remains stateless.
- No social login, MFA, email verification, token revocation/refresh, or frontend account recovery is included. TLS, rate limiting, and production secret management remain deployment responsibilities. Optional PostgreSQL integration tests require `TEST_DATABASE_URL`.

## Frontend authentication and application shell

- The React frontend now restores authenticated sessions from a short-lived bearer token, fetches the current persisted user/role, supports login and user-only public signup, logs out, and returns to login when the API rejects an expired or invalid session. Signup does not expose elevated role selection.
- The branded SafeSite Risk Intelligence shell provides responsive navigation for Overview, Safety Incidents, Alerts, Zone Analytics, and AI Safety Analysis. AI Safety Analysis is the sole primary persisted image upload surface; Safety Incidents displays Observation History. The stateless experimental viewer is no longer mounted in the normal app. Overview, alerts, and zone analytics consume protected database-backed APIs.
- Safety Officer/Admin users see alert lifecycle controls. Regular users do not see those controls, while backend authorization remains authoritative. Persisted observation images are fetched with bearer authentication so evidence lineage remains available in the UI.
- No frontend test runner is configured in `frontend/package.json`. Validation for this phase is `npm.cmd run lint` (completed with existing React lint warnings) and `npm.cmd run build` (passed).

Phase 5A renders the backend `safety_decision` directly in persisted assessment results and the experimental viewer; observation details display the stored decision snapshot where available. The renderer distinguishes `alert`, `warning`, `pending`, and `no_alert` with the backend reason, risk band, notification priority, and supporting findings. It labels the mapping as the current provisional system policy. No-finding wording now says only that no supported explicit PPE violation was detected and explicitly avoids claiming full compliance; non-hazard model classes are not called compliant. Older observations without a stored snapshot show an unavailable message. The experimental viewer remains labelled Experimental and stateless. There is still no frontend recurrence dashboard or automated component test harness.

## Shared Safety Decision Engine — Phase 1 (historical baseline)

- A pure policy in [`decision_engine.py`](../backend/app/decision_engine.py) now produces `alert`, `warning`, `no_alert`, or `pending` with a deterministic reason, highest completed risk band, notification priority, version, and one evidence item per supported finding. It consumes existing hazard/assessment objects and does not recalculate severity, likelihood, exposure, or risk scores. Low/Moderate/High/Critical remain 1–19/20–39/40–69/70–100.
- **Provisional application policy `milestone2-decision-v1-provisional`, requiring mentor confirmation:** Low → warning/routine, Moderate → warning/medium, High → alert/high, Critical → alert/urgent. This is an explicit *notification* choice, separate from severity and risk scoring, not a regulatory rule. It permits a supported violation to yield a warning instead of an alert. The highest band across simultaneous completed findings decides the aggregate outcome; all findings stay in supporting evidence. Missing or inconsistent scoring yields `pending` for the whole decision; a completed scan with no supported explicit violation yields `no_alert`, explicitly **not** confirmed site safety.
- Standard JSON and image assessment responses and the experimental image response expose the same `safety_decision` shape. The experimental `alert.alert_recommended` compatibility flag means only outcome `alert`; use `safety_decision.outcome` to distinguish warning, pending, and no-alert. LangGraph routes alert/warning to review and pending to its pending branch without side effects.
- **At the end of Phase 1**, persistence still created an open `Alert` for every supported violation, including warning/pending decisions. Phase 2 below changed *new* alert creation without rewriting historical rows. The frontend legacy Boolean alert display remains unchanged; standard detector `hazard_labels` still collapse same-type detections. No notification delivery was added.
- The policy remains provisional and mentor sign-off is still required. Phase 1 did not change model/data/training code.

## Alert Policy & Persistence Reconciliation — Phase 2

- New standard JSON/image observations persist the shared decision snapshot (outcome, reason, risk band, notification priority, evidence, policy version) in existing `Observation.raw_metadata`. Each supported hazard retains raw evidence, its assessment (completed or pending), and a per-finding decision in existing hazard `evidence` JSONB. No schema change or migration was required; `no_alert` observations also retain their decision in history. No outcome is represented as proof of full scene safety.
- An overall `alert` outcome creates actionable `Alert` rows only for findings the same shared policy individually rates `alert`. A warning sibling remains in history without an alert; if any supported finding is unscored/inconsistent, the *overall* result is `pending` and creates no new alert. New `warning`, `pending`, and `no_alert` observations produce no actionable alert rows. Existing IDs/statuses/timestamps and forward-only lifecycle/RBAC are unchanged. Repeated manual create requests return an existing row first; new manual creation is policy-gated. Historical rows are neither deleted nor rewritten.
- Alert detail APIs expose the stored finding decision reason, notification priority and policy version when present; legacy alerts may have null values. Zone analytics continue counting supported persisted hazard records and risk assessments, independent of whether an alert row exists. Alert counts still reflect actual rows, including historical rows.
- At the end of Phase 2, the Low/Moderate → warning and High/Critical → alert mapping remained **provisional, not mentor-approved**. Production notification delivery, exact duplicate-image protection, historical recurrence escalation, temporal worker tracking, frontend four-outcome presentation, live PostgreSQL verification, and model/data/training changes were not part of that phase. Observation history supports human review, but no dedicated warning/pending work queue was introduced.
- Verification: focused policy/persistence/analytics/auth/API suite **78 passed**; full backend suite **143 run, 2 skipped, no failures**. The two skipped tests require `TEST_DATABASE_URL` for disposable PostgreSQL integration. `git diff --check` passed (Git reported only line-ending conversion warnings); trailing-whitespace checks included the new untracked files.

## Exact Duplicate-Image Protection — Phase 3

- The persisted `POST /assessments/image` route extracts and validates the original upload bytes, then computes SHA-256 before detector inference, image storage, or database writes. It stores the lowercase digest in `Observation.raw_metadata.image.sha256` and the normalized caller-supplied submission inputs in `raw_metadata.image_submission`. It hashes neither annotation output nor decoded/resized model input.
- The supported duplicate scope is **the same explicit `observation_id`, exact original bytes, and unchanged work area/people override/duration/repeated-count inputs**, when the database is configured. `observation_id` is the only reliable submission identity currently represented; `work_area` is free text and is not an inspection/site identifier. A retry with the same ID, bytes and inputs receives HTTP `409` with `detail: {"code":"duplicate_image_submission","observation_id":"...","message":"This exact image submission already exists."}`. Reusing the ID with changed bytes or inputs receives the existing observation-ID conflict. A different observation ID accepts the same bytes as a distinct submission. Uploads without an explicit ID receive a new generated ID and cannot currently be recognized as retries. The default frontend upload path has this limitation unless the user supplies an observation ID. Without a configured database, the image route stays stateless and no persisted duplicate check applies.
- Duplicate lookup occurs before inference. The existing observation primary key arbitrates concurrent requests with the same ID at the first database flush; on an integrity race the endpoint rolls back, re-reads the committed winner, and returns the same duplicate response when the fingerprint and inputs match. Image files are written only after the first flush, so a losing same-ID request cannot overwrite the winner's files. This protects persisted rows/alerts/analytics for the supported scope, but does **not** serialize uploads with different IDs or provide global image-hash uniqueness. No new column, index, table, migration, or historical backfill is needed; existing rows without a digest remain valid and return an ordinary ID conflict if their ID is reused. PostgreSQL race behavior remains unverified without a disposable `TEST_DATABASE_URL`.
- A confirmed retry creates no new observation, hazard, assessment, recommendation, alert, or zone/violation event and leaves the original record intact. It does not increment `repeated_count` or represent historical recurrence. Phase 1/2 `alert`/`warning`/`pending`/`no_alert` decisions and notification thresholds remain unchanged. The experimental Safety Visualizer remains stateless and outside this persisted duplicate check.
- Verification: focused image/API/policy/experimental suite **68 passed**; full backend suite **150 run, 2 skipped, no failures**. The two PostgreSQL integration tests skipped because `TEST_DATABASE_URL` was not set. `git diff --check` passed (line-ending conversion warnings only). Tests use a recording session for duplicate and simulated primary-key-race behavior; no live PostgreSQL concurrency claim is made.

## Historical PPE-Violation Recurrence Analytics — Phase 4

- Authenticated `GET /analytics/work-area-recurrence` calculates informational history from persisted observations and supported hazard records. The recurrence key is **trimmed named `work_area` + canonical supported `hazard_type`**. A group counts **distinct `observation_id` values**, not hazard rows: one observation is observed; two or more distinct observations are repeated. The response includes contributing observation IDs, per-area summaries, deterministic ranking, and the number of named areas with repeated violations. Existing `/analytics/zones` violation totals still count hazard rows; those totals and recurrence counts have different units.
- Leading/trailing work-area whitespace is removed. Null, blank and `Unspecified` work areas are excluded from named-area recurrence. Case, punctuation and internal spelling remain distinct; there is no fuzzy matching, aliasing or site/zone identity inference. Only historical label/type pairs matching the existing supported detector-label-to-canonical-hazard mapping count as evidence; malformed or unsupported rows are excluded. A hazard-heavy work area means a named area with more recorded distinct observations in this view, not an accident-prone zone or accident probability.
- Optional timezone-aware `start` and `end` query bounds filter `Observation.observed_at` using **`start <= observed_at < end`**. Omitted bounds mean unbounded history, not an approved safety-policy duration; the effective supplied bounds are returned as UTC timestamps or null. Reversed/equal bounds or naive datetimes return 422. Historical timestamps and records are untouched.
- Phase 3 rejected exact image retries create no persisted observation and therefore cannot add recurrence. Equal image hashes across different observation IDs are not globally excluded: separate assessments may reuse an image, while legacy or JSON observations may have no hash. This view never reads or writes the caller-supplied `Observation.repeated_count`; it does not change likelihood, risk score, notification priority, shared decision, alert creation or persistence. No recurrence table, counter, column, index or migration was added. The experimental Safety Visualizer remains stateless and outside persisted recurrence history.
- Verification: focused recurrence/zone/duplicate/policy suite **37 passed**; full backend suite **165 run, 2 skipped, no failures**. `TEST_DATABASE_URL` was not set, so the PostgreSQL integration tests did not run. `git diff --check` passed. Live PostgreSQL query behavior remains to be verified. First-class Site/Zone/Inspection identity and validated location aliases remain future work; no worker-specific or accident-outcome claim is supported.

## Frontend Safety Semantics and Shared Decision Display — Phase 5A

- Persisted image/JSON assessment results and the experimental Safety Visualizer render the backend's `safety_decision` with distinct Alert, Warning, Pending Assessment, and No Actionable Alert states. The UI displays the backend reason, risk band, notification priority and available supporting evidence; it does not recompute the decision. The current Low/Moderate and High/Critical notification mapping remains provisional and unchanged.
- “Compliant Site Conditions,” the experimental generic no-alert banner, “Context / Compliant,” and “No Action Required” no-finding cues were replaced with evidence-safe language. No explicit supported PPE violation found is not proof that all PPE is present or that a site is safe. The experimental route stays labelled Experimental, stateless and separate from persisted assessment; no database writes were added.
- Observation history shows the persisted decision snapshot from `raw_metadata.safety_decision` when present. Older rows without a valid snapshot show “Decision snapshot unavailable” and are not reclassified. The caller-supplied scoring repetition input is labelled separately from Phase 4 historical recurrence. No backend API, schema, policy, scoring, persistence, duplicate, recurrence, model or dataset change was made.
- Verification: `npm.cmd run build` passed (includes `tsc -b`); `npm.cmd run lint` exited 0 with six pre-existing React warnings in unrelated files. No component test runner or component tests exist. `git diff --check` passed. Live PostgreSQL and connected end-to-end verification remain Phase 5B; frontend recurrence integration is still pending.

## Phase 5B-2 disposable PostgreSQL and connected verification (2026-11-05)

- Created separate, initially empty local PostgreSQL 18 databases `safesite_integration_test` and `safesite_demo`; the repository-root `.env` database was not used as a target. With process-local `DATABASE_URL` and `TEST_DATABASE_URL` pointed only at the integration database, `python -m unittest backend.tests.test_database_integration -v` passed **2/2**. Its teardown downgraded the application schema to base; the integration database retained no SafeSite application tables (only `alembic_version`). The full backend suite was not rerun in this phase.
- Applied `alembic upgrade head` to `safesite_demo` and verified `alembic current` = `0002_user_accounts`. Bootstrapped an Admin with a hidden password; public signup created two `user` accounts, and the Admin role API promoted one to `safety_officer`. Login and `/auth/me` succeeded. Anonymous protected reads returned 401; the regular user could read analytics but received 403 for alert and role mutations; the Safety Officer passed the alert-write role guard, performed alert lifecycle changes, and the Admin changed a role and dismissed an alert.
- Live YOLO `POST /assessments/image` submissions: `m2-demo-img-clean` used [`construction-1023`](../datasets/evaluation/construction-site-safety-v1/valid/images/construction-1023-_jpg.rf.934b9e434de66c21149aaa3d2d7680c5.jpg) with people/duration/repetition inputs 1/1/0 and returned `no_alert`, 0 supported hazards, with the explicit “does not confirm site safety” reason. `m2-demo-img-violation` used [`-1079-`](../datasets/evaluation/construction-site-safety-v1/valid/images/-1079-_png_jpg.rf.b5df117d2f459522987e48fdf0f80564.jpg) with 2/30/3 and returned one `missing_safety_vest` finding, Moderate `warning`, and no alert. `m2-demo-img-alert` used [`ppe_0665`](../datasets/evaluation/construction-site-safety-v1/valid/images/ppe_0665_jpg.rf.885665684b4ab7e7fed9393d499f3d1a.jpg) with 10/240/5 and returned vest and helmet findings, Critical `alert`, and two open alert rows. These are detector outputs for selected evaluation images, not independent confirmation of scene safety or detector correctness. Test-supplied exposure/repetition inputs selected the displayed risk bands.
- Deterministic JSON submissions verified Low `warning` (two distinct `no_helmet` observations in `Recurrence Bay`, both `repeated_count=0`), Critical `alert`, incomplete `pending`, and `no_alert`. Direct SQL and observation/alert APIs confirmed observation → hazard → completed/pending assessment → alert linkage where applicable, decision snapshots and image SHA-256/box metadata. Warning and pending created no actionable alerts. The standard persisted route did not create `safety_recommendations` rows, consistent with its current schema-only recommendation persistence.
- Alert 2 transitioned `open → acknowledged → resolved` via Safety Officer with acknowledgment/resolution timestamps. Alert 3 transitioned `open → dismissed` via Admin; dismissal status persisted but the schema/API has no `dismissed_at` timestamp. One alert remained open. `/analytics/zones` reported 7 hazard-row violations across three named work areas, Low 2 / Moderate 1 / Critical 3 / pending 1 assessments, and open 1 / unresolved 1 / resolved 1 alerts. `/analytics/work-area-recurrence` reported `Recurrence Bay` + canonical helmet hazard as 2 distinct observations, repeated=true, with both IDs; it remained informational and did not change scoring or alerts.
- An exact image retry with the original bytes, explicit `m2-demo-img-violation` ID and unchanged inputs returned HTTP 409 with `duplicate_image_submission`. Before and after that retry, SQL counts remained 8 observations / 7 hazards / 7 assessments / 3 alerts; vest recurrence in `Demo Yard` remained 2 distinct observations. Concurrent same-ID requests were **not** exercised against PostgreSQL. Experimental API inference and browser runs showed `pending`, `warning`, `alert`, and `no_alert` presentations while counts remained unchanged. A subsequent intentional persisted browser upload increased observations to 9, with hazards/assessments/alerts still 7/7/3.
- Connected frontend login, persisted upload result, expanded history, alert register, zone analytics and Experimental Safety Visualizer were exercised in the browser. The decision display showed all four outcomes, backend reasons, priorities, risk bands and available evidence; no-finding UI avoided a compliance/safety claim. The experimental view retained its label and stateless boundary. There is no recurrence dashboard or automated frontend component test harness.
- **Defect observed in Phase 5B-2, fixed and verified in Phase 6A below:** a multi-class persisted image assigned the overall maximum violation confidence (0.7676) to both vest and helmet hazard rows; the highest matching helmet box confidence was 0.7343. The Phase 5B-2 demo rows remain historical and were not rewritten. At the time of this verification there was no dismissal timestamp; Phase 6A added one for future transitions. Other limits persist: no persisted standard-route recommendation rows, free-text work-area identity, generated-ID retry scope, unverified live concurrency, provisional notification mapping, model recall/class gaps and no notification delivery. Demo database was deliberately left intact. Process-local demo JWT secret and temporary generated account passwords were not written to the repository; a later session needs its own secure backend secret and operator-managed account access.

## Phase 6A correctness and audit hardening (2026-11-05)

- **Confidence:** The persisted image route maps each supported detection box to its canonical hazard type and uses the maximum confidence within that type. For example, two `NO-Hardhat` boxes at 0.61/0.73 and one `NO-Safety Vest` box at 0.77 produce helmet 0.73 and vest 0.77; unrelated person or PPE boxes cannot raise another hazard's confidence. Hazard evidence now retains only the matching raw boxes, while observation metadata keeps all original boxes. Observation-level `detection_confidence` remains the image-wide violation maximum. No scoring threshold, detector inference, or historical row was changed.
- **Alert lifecycle:** Migration `0003_alert_dismissed_at` adds nullable timezone-aware `alerts.dismissed_at` after `0002_user_accounts`. A transition to `dismissed` sets it; acknowledgment and resolution timestamps remain distinct and are preserved. Alert list/detail/status responses expose it. Older dismissed alerts have a null value because the historical dismissal instant is unknown. The preserved `safesite_demo` database still needs a forward upgrade before using this backend; it was not modified in Phase 6A.
- **Password creation:** Signup schema and central scrypt hashing require at least eight characters. The Admin bootstrap uses the same hashing rule and prompts accordingly. The signup form communicates and checks the minimum; login has no new minimum, so stored short historical credentials remain usable. Existing 1024 UTF-8 byte hash limit remains. No new character-composition policy was added.
- **Verification:** Focused image tests 29/29, auth tests 11/11, alert API tests 5/5, persistence tests 10/10 passed. Full backend suite 172 run, 3 PostgreSQL tests skipped when `TEST_DATABASE_URL` was unset. Frontend `npm.cmd run build` passed (`tsc -b` included), and lint exited 0 with six pre-existing warnings. A newly created disposable `safesite_phase6a_da2d96f453` PostgreSQL database was upgraded from base through `0002_user_accounts`, seeded with one historical dismissed alert, then upgraded to head `0003_alert_dismissed_at`; the old row remained readable with null dismissal timestamp. All three PostgreSQL integration tests passed, including persisted two-class confidences and matching detection evidence; their teardown downgraded only that disposable database to base. `git diff --check` passed. No real YOLO inference was used in the new confidence integration test; a deterministic detector exercised the persisted image route.
- **Remaining limits:** Historical confidence values and dismissal events are not backfilled. The demo database remains at its earlier migration version until an operator upgrades it. Live concurrency, actual model accuracy, pending-assessment completion, notification delivery, and mentor approval of policy thresholds remain open. Phase 6B can begin without changing Phase 6A semantics.

## Phase 6B pending risk assessment completion (2026-11-05)

- **Workflow and authorization:** `PATCH /assessments/{assessment_id}/complete` requires an authenticated Safety Officer or Admin. Anonymous and ordinary users receive 401 and 403. Unknown assessments return 404; already completed or superseded rows return a structured 409. The endpoint accepts only optional `people_count >= 1`, `duration_minutes >= 1`, and `repeated_count >= 0`; missing required values produce 422, and conflicting replacements for existing Observation values produce a structured 409. A later sibling assessment can be completed with `{}` after the shared Observation context has been supplied. Severity is never operator-editable.
- **Scoring and decision:** The existing `RiskAssessment` row is updated from pending to completed using `SiteRiskAgent.assess_hazard` and its unchanged severity, likelihood, exposure, score, and band rules. The shared `evaluate_safety_decision` policy is rerun over all supported findings in that Observation, updating the observation snapshot and per-finding decision evidence. A partially completed multi-finding Observation remains overall `pending`; an actionable alert is created only when the overall decision becomes `alert` and a finding is alert-grade. A completed supported finding normally yields `warning` or `alert`, not `no_alert`. Historical work-area recurrence is never used to fill the caller-supplied scoring `repeated_count`.
- **Persistence and audit:** The original Observation, hazard rows, image hash/geometry, and detection evidence remain in place. Missing context is filled on the Observation; the same assessment receives score fields and timezone-aware `assessed_at`. Existing `Observation.raw_metadata` JSONB stores an `assessment_completions` entry keyed by assessment ID with previous pending status, completion time, authenticated user ID, submitted/new/resolved context. No new table, column, or migration was needed. The existing alert creation helper returns historical alerts unchanged and prevents repeated creation for the same hazard. PostgreSQL Observation row locks serialize completion attempts for that Observation; a two-request live test yielded one 200 and one 409 with one alert. Concurrent interaction with separate manual alert creation was not tested.
- **Frontend:** Observation History displays missing context fields and a Complete Assessment action only to Safety Officer/Admin. Existing values appear read-only. On success, it refreshes history without a page reload, shows persisted score components and the updated shared decision, and identifies linked alert IDs. The initial upload result is cleared if it belongs to the updated Observation, avoiding a stale pending panel. Regular users can still review history but cannot submit completion. No frontend component-test harness exists; TypeScript/build and lint provide the automated frontend checks.
- **Verification:** Focused auth 12/12 and disposable PostgreSQL integration 9/9 passed. Integration coverage includes warning/no alert, alert linkage, duplicate and concurrent completion, legacy alert preservation, input/auth validation, multi-finding pending policy, history, analytics, audit metadata, and evidence preservation. Full backend suite: 179 run, nine PostgreSQL tests skipped with `TEST_DATABASE_URL` unset; no failures. Frontend build including `tsc -b` passed; lint exited 0 with six existing warnings. `git diff --check` passed. Integration teardown downgraded only the newly created disposable `safesite_phase6b_8efc6bb14a` database to base.
- **Demo migration:** After disposable verification, `safesite_demo` was checked at `0002_user_accounts` and forward-upgraded to current head `0003_alert_dismissed_at`. Before/after counts matched exactly: 9 Observations, 7 hazards, 7 assessments, 3 alerts, and 3 user accounts. Its Phase 5B records were not modified or deleted. No Phase 6B schema migration was introduced.
- **Remaining limits:** Completion is restricted to persisted supported PPE findings. Completed historical assessments cannot be casually corrected; existing historical alert rows remain untouched. The experimental route remains stateless. No notification delivery, validated site/zone identity, production model improvement, or approved notification threshold was added. Phase 6C can begin separately.

## Phase 6C production AI Safety Analysis (2026-11-06)

- **Primary route and UX:** The normal AI Safety Analysis page now uses the existing authenticated `POST /assessments/image` client and one shared `ImageUploader`/`AssessmentResults` path. Safety Incidents is the persisted Observation History destination. The previous Experimental Safety Visualizer component is unmounted from normal routing; `#experimental` and the old query-tab alias redirect to the persisted `#analysis` view. The stateless backend `/experimental/safety/detect` route and its development-only frontend component remain in source, but no normal navigation invokes them. No backend or schema behavior changed.
- **Evidence and context:** The page shows original observation ID, annotated image, canonical supported PPE findings, per-hazard detector confidence, backend score components/bands and the shared four-outcome decision. The upload form calls work area and exposure/repetition operator context; people count is an optional operator override, while the backend may use detected persons if present. A single image does not establish duration or recurrence. No-finding copy explicitly avoids a compliance or safety claim. A database-unavailable state blocks the normal upload UI.
- **Pending, alerts and history:** Safety Officer/Admin sees the reused Phase 6B completion form directly below a pending result when the persisted detail loads; everyone has a History path. Completion refreshes the saved record and shows the returned score and shared decision without re-upload. Alert-grade results query existing `/alerts?observation_id=...` and link IDs to Alert Register; no frontend alert creation exists. Every successful upload refreshes Observation History. Zone analytics continues to read persisted hazards/assessments.
- **Connected verification:** Confirmed `safesite_demo` and Alembic head `0003_alert_dismissed_at` before starting. Used a process-local JWT secret, real checkpoint, and a temporary Safety Officer account that was deactivated after sign-out. The browser showed no Experimental/Testing Bench copy in the normal page. The reviewed clean image yielded `no_alert`, zero supported findings and a saved Observation. A second reviewed image yielded one vest finding at 60.1% and `pending`; inline completion with recorded people count 5, operator duration 10 minutes and repetition 0 returned Moderate score 24, `warning`, and no alert. The reviewed multi-class image with operator context 10/240/5 returned `alert`, Critical scores 80/100, vest confidence 76.8%, helmet confidence 73.4%, and linked open Alerts #4/#5. History displayed the saved no-finding observation; Alert Register displayed the two new alert rows; Zone Analytics loaded 10 persisted hazard rows with the new work-area totals. Backend request logs showed the primary UI called `/assessments/image`, `/assessments/8/complete`, observation, alert and analytics APIs, with no experimental call.
- **Direct database check:** Three new Observations were present. The alert image persisted vest confidence 0.7676 and helmet confidence 0.7343 in separate hazard rows, plus two completed Critical assessments and two open alert rows. The pending image retained one vest hazard and the same assessment row completed Moderate at score 24; no alert was linked to it. `safesite_demo` was not downgraded or reset, and no earlier records were deleted. The temporary browser account was deactivated; its test Observations and Alerts remain as explicit demo evidence.
- **Validation and limits:** Frontend build includes `tsc -b`; lint and `git diff --check` results are recorded in the activity row below. No frontend component test harness exists. This connected check used selected evaluation images and operator-supplied scoring context, so it does not establish model accuracy or a validated safety policy. The regular-user pending form boundary relies on existing backend RBAC and earlier tests; browser verification here used a Safety Officer. No recurrence UI, notification delivery, stable demo credentials, or new site/zone identity was added.

## Phase 6D recurrence analytics UI (2026-11-06)

- **Navigation and contract:** Added a dedicated `#recurrence` page beside Zone Analytics. The typed client sends only the backend's optional `start` and `end` parameters and renders its canonical hazard groups, distinct observation counts, repeated flags, ranked work areas, and contributing observation IDs. Summary cards are presentation summaries of the response. The existing `/analytics/zones` page and its hazard-row totals are unchanged.
- **Window and wording:** No bounds means all history; local date/time inputs are converted to timezone-aware ISO timestamps. The page shows effective bounds returned by the backend and explains inclusive start/exclusive end. Clear restores all history. Ranking lists only areas with a repeated group but uses the backend's broader distinct-observation metric, explicitly labelled as including any supported PPE finding in those areas. Group cards show both repeated and observed-once records; history navigation opens the existing observation list. Null/blank/Unspecified areas remain excluded by the backend. Free-text case and spelling are retained. Recurrence is informational observation history, not worker/site behavior, accident risk, caller-supplied `repeated_count`, scoring, or alert escalation.
- **Connected verification:** Confirmed the preserved `safesite_demo` database and migration head `0003_alert_dismissed_at` without destructive tests. A temporary existing Safety Officer account was activated for the browser session and deactivated afterward. The browser showed three repeated area/hazard groups, each with two distinct IDs; `Recurrence Bay`/Missing Safety Helmet showed `m2-demo-json-warning-a` and `m2-demo-json-warning-b`. A valid 2026-11-05 through 2026-11-07 local time window loaded, an empty 2035 window showed zero counts and evidence-safe empty copy, and Clear restored all history. View Observation History navigated to the persisted list. Existing Zone Analytics still loaded its 10 hazard-row total. No observation, hazard, assessment, or alert rows were written by the recurrence view.
- **Validation and limits:** Frontend build (`tsc -b` and Vite), lint, and `git diff --check` passed. There is no frontend component test harness. The dedicated view cannot prove worker or site identity, validate free-text areas, or predict accidents. History navigation does not yet open a specific observation by ID. No backend, schema, model, dataset, scoring, or policy change was made.

## Phase 6E branding and local mentor demo (2026-11-06)

- **Brand and access:** Shared shield/hardhat SafeSite mark now appears on auth and shell screens; the template favicon was replaced. The primary navigation orders Overview, persisted AI Safety Analysis, Safety Incidents, Alert Register, Zone Analytics, and Recurrence Analytics. Only Vite development mode shows a demo-role hint; passwords remain in the [local demo guide](./local-mentor-demo.md). Signup still requires eight-character new passwords; login and backend RBAC are unchanged.
- **Demo bootstrap:** [`bootstrap_demo_accounts.py`](../backend/app/bootstrap_demo_accounts.py) targets only local PostgreSQL `safesite_demo`, checks migration `0003_alert_dismissed_at`, and creates/verifies Admin, Safety Officer, and User identities without overwriting conflicts. First run created 3; second run reported 0 created/3 matched. [`start_demo_backend.ps1`](../scripts/start_demo_backend.ps1) launches the demo database and checkpoint with a process-local JWT secret. Existing operator credentials were untouched.
- **Connected walkthrough:** Before the run, `safesite_demo` held 12 observations, 10 hazards, and 5 alerts. Browser login worked for all three roles. A Regular User saw no alert lifecycle controls and received 403 for alert mutation, pending completion, and role mutation. An Admin changed the dedicated demo User role and restored it, both with HTTP 200. As Safety Officer, three reviewed image submissions through the persisted UI created a no-finding record, a one-vest pending record, and a two-class alert-grade record. The no-finding page avoided a compliance claim; the pending record completed in place to Moderate 24/Warning with no alert; the two-class result showed helmet 73.4%, vest 76.8%, Critical scores 100/80, annotation, and linked alerts. The two new alerts were acknowledged/resolved and dismissed respectively; timestamps persisted after Refresh, and prior open alerts remained. History showed saved records/images/score/decision. Zone Analytics showed 13 hazard rows, area metrics, common violation and risk distribution. Recurrence showed four repeated groups; `Phase 6E Demo Bay` vest recurrence had two distinct observation IDs. A bounded filter and Clear worked. Final SQL showed 15 observations, 13 hazards, 13 assessments, 7 alerts, and three active demo accounts at the unchanged migration head.
- **Wording and limits:** Visible primary views use friendly canonical PPE labels and omit raw detector labels where practical; the alert list strips source-label debug suffixes, shows lifecycle timestamps, and preserves backend status and decision authority. The main UI does not claim confirmed safety or notification delivery. Historical alert rows created before dismissal timestamp support can still have null `dismissed_at`. Raw source labels remain in backend evidence and some backend-generated assessment explanations. The demo walkthrough used selected evaluation images and operator-supplied context; it does not validate model accuracy or certify safety policy. No Site/Zone/Worker identity was introduced.
- **Validation:** Focused demo-bootstrap/auth suite: 15 passed. Frontend build/TypeScript, lint, and `git diff --check` results appear in the activity row below. No frontend component test harness exists. No material backend application logic changed, so the full backend suite was not rerun solely for the demo helper.

## Normal local application environment transition (2026-11-06)

- **Database identity and migration:** The configured server was PostgreSQL 18.6 on local `::1:5432`. `safesite_local` did not exist; it was created fresh and verified to have zero public tables. Alembic `upgrade head` applied revisions `0001_initial_schema`, `0002_user_accounts`, and `0003_alert_dismissed_at`. Direct SQL then confirmed `current_database() = safesite_local` and zero observations, detected hazards, risk assessments, alerts, and users before bootstrap.
- **Accounts and startup:** A separate idempotent local helper created `admin@safesite.local`, `officer@safesite.local`, and `user@safesite.local`; a second run created zero accounts and matched all three. It checks the local host, database identity, and current repository migration head and refuses to overwrite conflicting accounts. New migration and backend startup scripts target only `safesite_local`, use a process-local JWT secret and the existing checkpoint, and leave the root `.env` unchanged. Normal login no longer shows the old developer demo-role hint. The README and [local setup](./local-setup.md) make this the primary environment; the [mentor fallback](./local-mentor-demo.md) remains available.
- **Connected clean state:** Browser login as the normal local Safety Officer succeeded. Overview showed zero activity; History had no observations; Alert Register had no alerts; Zone Analytics had zero findings/no area; Recurrence Analytics had no repeated groups and an evidence-safe empty state. The History empty instruction was corrected to point to AI Safety Analysis.
- **First actual upload:** One reviewed image was submitted through the persisted AI Safety Analysis UI as `local-first-image-20261106`, work area `Local Review Area`. The current checkpoint found Missing Safety Vest with matching detection confidences approximately 0.6013 and 0.5880, displayed an annotated image, and returned `pending` because duration/repetition were absent. The stored hazard confidence is 0.6013, matching the maximum matching vest detection; image metadata retains its SHA-256, geometry, and shared decision. Direct SQL showed exactly 1 Observation, 1 DetectedHazard, 1 pending RiskAssessment, 0 Alerts and 3 users. History showed the saved image, decision and confidence; Zone Analytics showed one hazard and one pending assessment; Recurrence Analytics marked the group observed once. No fake/sample analytics rows were inserted and no pending completion was performed.
- **Preservation and limits:** `safesite_demo` remained at `0003_alert_dismissed_at` with 15 observations, 13 hazards, 13 assessments, 7 alerts and 7 users. Existing project-level image files are keyed by Observation ID without database namespacing; intentionally reusing an ID across databases could overwrite an image file. This environment transition did not change model, scoring, alert policy, duplicate handling, recurrence, or authentication rules. Focused local-bootstrap tests passed 3/3; frontend build/TypeScript and lint passed with six existing lint warnings. No full backend suite was rerun because backend application behavior was unchanged. `git diff --check` is recorded in the activity row below.

### Local safety-data reset (2026-11-06)

Direct SQL confirmed `current_database() = safesite_local` and migration `0003_alert_dismissed_at` before cleanup. Three actual image Observations were present at cleanup time, including two uploads after the first connected verification: 3 observations, 2 detected hazards, 2 risk assessments, 0 alerts, and 3 active local users. In one transaction, the local safety tables were cleared in foreign-key order; afterward they held 0 observations, hazards, assessments, alerts, recommendations, and workflow runs, while all three local accounts remained active. The three associated storage directories were checked against each original image's recorded SHA-256 and verified absent from `safesite_demo` references before their six image files were removed. A Safety Officer browser login confirmed empty Overview, Safety Incidents, Alert Register, Zone Analytics, and Recurrence Analytics; no image was uploaded afterward. Read-only checks showed `safesite_demo` still at 15 observations, 13 hazards, 13 assessments, 7 alerts, and 7 users. No schema, model, scoring, or application behavior changed.

### Phase 7A: Safety Reports and work-area naming (2026-11-06)

- **Work-area correction:** The upload form labels the optional field **Work Area / Zone** and explains that blank means unassigned. History shows **Unassigned work area** for blank/legacy placeholder values. Safety Officer/Admin can assign or correct an existing Observation through `PATCH /observations/{observation_id}/work-area`; the backend trims names, rejects blank/placeholder input and limits new names to 255 characters. It changes only the Observation's `work_area`, `updated_at` and a `raw_metadata.work_area_changes` audit list containing old/new names, actor and time. Existing risk inputs, assessments, decisions and alerts are untouched. Regular users receive 403. No migration was needed.
- **Reports:** Authenticated `GET /reports/work-areas` lists actual named persisted areas. `GET /reports/safety` and `/reports/safety.pdf` share one structured report calculation and the same explicit filters: optional timezone-aware `start <= observed_at < end`, all history when omitted, all areas or multiple exact named areas, and optional unassigned observations for selected-area scope. The new Reports page previews totals, decision counts, supported PPE finding rows, risk distribution, per-area counts and ties, distinct-observation recurrence, alert lifecycle, and detailed findings before download. Server PDF rendering uses `fpdf2` and the same filtered payload; original/annotated images are not embedded. Both preview and PDF state that recorded/model-supported findings neither certify compliance nor establish overall safety. Work areas remain free text, with case/spelling variants distinct; no site identity, worker identity, accident prediction or recurrence-based scoring was added.
- **Connected verification:** `safesite_local` was confirmed empty before four real image submissions through the normal UI/API. The first image had no area, appeared as **Unassigned work area** in History, then a Safety Officer assigned **Zone A** in the UI; the name survived reload, appeared in Zone Analytics and the Reports selector, and joined a two-observation Zone A vest recurrence after a different reviewed image was uploaded. Two further reviewed images created Zone B and Zone C observations with no supported findings. All-area report counted 4 observations, 3 supported findings, 2 Alerts and 1 pending assessment; Zone A counted 2 observations; Zone A + Zone B counted 3 and excluded Zone C; a future-period filter returned an evidence-safe empty report. The all-area, Zone A, Zone A + Zone B and empty-scope PDF endpoints returned `application/pdf` with nonempty `%PDF-` bytes. Extracted text from the Zone A and Zone A + Zone B PDFs contained the selected observations/areas and excluded Zone C. Direct SQL confirmed 4 observations, 3 hazards, 3 assessments, 2 alerts and 3 users, one work-area audit entry, and unchanged `safesite_demo` counts (15/13/13/7/7). These are real checkpoint outputs from existing images, not claims of model accuracy.
- **Post-verification cleanup:** After confirming `current_database() = safesite_local` and migration `0003_alert_dismissed_at`, the four Phase 7A IDs (`phase7a-unassigned-1`, `phase7a-zone-a-2`, `phase7a-zone-b-1`, `phase7a-zone-c-1`) were found to be the only local observations. Their 3 hazard rows, 3 assessments and 2 alerts were removed with the 4 observations in one transaction; there were no linked recommendations or workflow runs. All eight original/annotated image files in four SHA-256 ID-keyed directories were removed only after confirming metadata ownership and no ID/storage-key references in `safesite_demo`. Final local counts are 0 observations, hazards, assessments, alerts, recommendations and workflow runs, with 3 active local users. Read-only browser checks showed empty Overview, Incidents, Alerts, Zones, Recurrence and a working zero-count Reports preview; no image was uploaded. `safesite_demo` remained 15/13/13/7/7.
- **Verification and limits:** Focused reporting tests passed 12/12. The full backend suite passed 197 tests with 9 PostgreSQL-only tests skipped because `TEST_DATABASE_URL` was absent. A first parallel run hit `scrypt` memory errors while the live YOLO backend was active; rerunning without that competing process passed. Frontend build/TypeScript and lint passed (six existing lint warnings); `git diff --check` passed. Report aggregation currently loads matching persisted records in memory and has no pagination; PDF image evidence embedding and a validated Site/Zone entity remain future work.

## Chronological activity log

| Date | Phase/task | Work performed | Files/artifacts created or changed | Verification performed | Outcome | Decisions/blockers | Next action |
|---|---|---|---|---|---|---|---|
| 2026-11-02 | Held-out YOLO test evaluation | Evaluated the existing checkpoint on the existing 82-image test split. | `reports/model-evaluation/evaluate_yolo.py`; timestamped test evaluation outputs. | Report records 82 images, 806 instances, model/data hashes, class match, plots, metrics. | Baseline established. | Weak recall; test remains historical and is not for threshold tuning. | Use validation-only analysis for diagnosis. |
| 2026-11-02 | Validation error analysis | Compared eight confidence thresholds on validation only; performed IoU-matched FP/FN and representative annotation review. | `reports/model-evaluation/analyze_validation.py`; `outputs/validation-analysis-20261102T133016Z/`. | Report records 114 images, 733 GT instances, IoU >=0.50 and threshold metrics. | Error evidence captured; no production threshold change. | Annotation/domain and model limitations remain hypotheses except reviewed cases. | Investigate source data and split quality. |
| 2026-11-02 | Dataset expansion research | Compared public supplementary dataset candidates and licensing/access information. | `reports/model-evaluation/dataset-expansion-plan.md`. | Research summary saved with candidate mappings and source links. | Ultralytics Construction-PPE selected for inspection. | Image licensing and semantic scope require verification. | Acquire only official source after verification. |
| 2026-11-02 | Official dataset acquisition and inspection | Downloaded official archive and inspected YAML, splits, labels, class counts, dimensions, and hash. | `ultralytics-dataset-inspection.md`; `ultralytics-dataset-provenance.json`; local ignored dataset/archive. | ZIP CRC and annotation checks recorded; source archive hash captured. | Inspection complete; dataset not merged. | No image provenance manifest; ten orphan labels; ambiguous `none` and `no_gloves` scope. | Review duplicates, labels, and rights. |
| 2026-11-02 | Phase 2B quality review | Visually reviewed 13 duplicate pairs and six `no_gloves` examples; audited orphan labels and rights evidence. | `dataset-integration-readiness.md`, `licensing-review.md`, `outputs/dataset-review/` contact sheets and CSVs. | All candidate and sample rows accounted for; visual and filename-family notes recorded. | Integration readiness: not ready. | Nine test-scene overlaps, sampled glove-context mismatch, orphan association and photo rights unresolved. | Prepare auditable, non-mutating integration proposal. |
| 2026-11-02 | Phase 2C planning | Drafted class map, 13-pair/10-orphan quarantine manifest, complete proposed file-level manifest, split strategy, approval gates, and living milestone log. | `proposed-class-mapping.md`, `phase-2c-integration-plan.md`, `outputs/dataset-review/integration-plan/`, this log, README link. | CSV headers/counts, required paths, source/status boundaries, and Git ignore rules checked. No source files or tests were changed/run. | Proposal prepared only; dataset remains unmerged and training has not started. | Human/legal/publisher approval gates remain open. | Request written publisher provenance/policy clarification and legal/human review. |
| 2026-11-02 | Phase 2D Stage 1 — PPE class and annotation audit | Compared checkpoint/YAML IDs and app behavior; drafted explicit eight-class policy; counted matched labels; generated deterministic train/val/test representative contact sheets and review index; reviewed samples and recorded statuses; compared weaknesses against existing evaluation evidence. | `reports/model-evaluation/audit_ppe_annotations.py`; `ppe-annotation-policy.md`; `ppe-remediation-gap-analysis.md`; `ppe-stage-1-decisions.md`; `outputs/ppe-audit/` CSVs, JSON metadata, five sheets; this log. | Script run with `.venv-yolo/Scripts/python.exe`; 717 original and 1,416 supplementary matched images scanned; 39 sample rows across all three splits; orphan labels excluded; class counts and sample paths checked. No training/test/application tests run because this was a read-only data audit. | Stage 1 audit deliverables complete. No PPE remediation, merge, model change, threshold change, or production change occurred. | Original NO-Gloves and supplementary NO-Mask/NO-Vest are absent; sampled supplementary no_gloves scope is concerning; photo rights, duplicate groups, publisher codebook, and human policy approval remain unresolved. | Stage 2: obtain approvals/clarifications, then prepare a separate curated eligibility and split manifest without altering source files. |

| 2026-11-02 | Phase 2D Stage 2 source research and remediation planning | Created a 13-pair disposition register, documented nine train-to-frozen-test scene overlaps and four other scene-family pairs, catalogued ten unpaired orphan label files/93 rows, recorded bounded conclusions from the sampled no_gloves review, and compared primary-source dataset candidates and licensing evidence. Built a 26-class coverage matrix with NO-Gloves conditional and a non-mutating future curation strategy. | `phase-2d-supplementary-review-decisions.md`; `phase-2d-dataset-source-research.md`; `phase-2d-class-coverage-matrix.csv`; `phase-2d-remediation-plan.md`; this log. | Checked linked local evidence paths, source URLs in research, 26 taxonomy rows and consistent CSV headers; no datasets or source annotations changed, no download/merge/split/model/application work performed. | Planning/research deliverables prepared. Stage 2 is not complete and no candidate data is approved for training. | Underlying photo rights, author access/codebooks, scene-group disposition, orphan associations, NO-Gloves task/context suitability, and human approval remain unresolved. | Obtain primary-source data/provenance and licensing clarification; human-review candidate labels and duplicate groups before any Stage 3 proposal. |

| 2026-11-04 | Alert persistence and lifecycle | Completed the backend persistence slice: persisted PPE violation alerts are linked to detected hazards and assessments, duplicate creation is idempotent, alert history/detail/create routes are exposed, and guarded status transitions record acknowledgment/resolution timestamps. The experimental image route remains explicitly stateless. | [`backend/app/persistence.py`](../backend/app/persistence.py); [`backend/app/main.py`](../backend/app/main.py); [`backend/tests/test_persistence.py`](../backend/tests/test_persistence.py); [`backend/tests/test_alert_api.py`](../backend/tests/test_alert_api.py) | `.venv-yolo/Scripts/python.exe -m unittest backend.tests.test_persistence backend.tests.test_alert_api backend.tests.test_api -v`: 17 passed. PostgreSQL integration remains skipped unless `TEST_DATABASE_URL` is configured. | Alert persistence/lifecycle backend work is complete for this phase. | No zone analytics, frontend changes, notification delivery, or live PostgreSQL verification was added. | Proceed to the separate zone-analytics phase. |

| 2026-11-04 | Zone-level safety analytics backend | Added deterministic database-backed analytics over persisted supported PPE violation records: counts by temporary `work_area`, highest/lowest areas, common violations overall/per area, risk distribution including pending, alert status counts, and source observation/detected-hazard lineage. Added empty-dataset behavior and API coverage; no frontend or model/data changes. | [`backend/app/analytics.py`](../backend/app/analytics.py); [`backend/app/main.py`](../backend/app/main.py); [`backend/tests/test_zone_analytics.py`](../backend/tests/test_zone_analytics.py); this log. | Focused zone analytics suite: 5 passed. Full backend suite: 114 passed, 2 skipped. | Backend analytics phase implemented. | `work_area` remains nullable free text, not a validated zone entity; live PostgreSQL integration and frontend dashboard remain future work. | Proceed to frontend dashboard integration after PostgreSQL-backed deployment verification. |

| 2026-11-04 | Backend authentication and role access | Added persisted accounts and migration, scrypt password hashing, short-lived signed JWT login, public user-only signup, operator-only first-Admin bootstrap, Admin role assignment, and role enforcement on safety and alert endpoints. Existing read-only safety/analytics APIs are available to any authenticated role. | [`backend/app/auth.py`](../backend/app/auth.py), [`backend/app/bootstrap_admin.py`](../backend/app/bootstrap_admin.py), [`backend/app/db_models.py`](../backend/app/db_models.py), [`alembic/versions/0002_user_accounts.py`](../alembic/versions/0002_user_accounts.py), [`backend/app/main.py`](../backend/app/main.py), [`backend/tests/test_auth.py`](../backend/tests/test_auth.py); this log. | Focused auth suite: 9 passed. Full backend suite: 123 passed, 2 skipped. | Backend auth flow and RBAC implemented. | PostgreSQL-backed migration/auth not exercised locally without `TEST_DATABASE_URL`; frontend not yet integrated. | Apply migration, bootstrap Admin, integrate frontend. |

| 2026-11-04 | Frontend authentication and SafeSite application shell | Added token-backed login/session restoration, user-only signup, logout/session-expiry handling, responsive branded navigation, role-aware alert controls, and Overview/Alerts/Zone Analytics pages connected to persisted APIs. Preserved the incident upload/history and AI analysis workflows; protected observation images now use bearer-authenticated blob requests. | [`frontend/src/App.tsx`](../frontend/src/App.tsx); [`frontend/src/auth/AuthContext.tsx`](../frontend/src/auth/AuthContext.tsx); [`frontend/src/auth/AuthPages.tsx`](../frontend/src/auth/AuthPages.tsx); [`frontend/src/components/AppShell.tsx`](../frontend/src/components/AppShell.tsx); [`frontend/src/components/OverviewPage.tsx`](../frontend/src/components/OverviewPage.tsx); [`frontend/src/components/AlertsPage.tsx`](../frontend/src/components/AlertsPage.tsx); [`frontend/src/components/ZoneAnalyticsPage.tsx`](../frontend/src/components/ZoneAnalyticsPage.tsx); [`frontend/src/api/client.ts`](../frontend/src/api/client.ts); this log. | `npm.cmd run lint`: completed with existing React lint warnings. `npm.cmd run build`: passed. No frontend test script is configured. | Frontend auth and shell foundation is complete for backend integration. | Backend remains authoritative for alert lifecycle permissions; production token revocation/recovery and a dedicated frontend test runner remain future work. | Integrate the login/signup frontend with deployment configuration, then continue dashboard refinement. |

| 2026-11-04 | Milestone 2 Phase 1 shared safety decision | Added one pure provisional four-outcome policy; integrated standard JSON/image and experimental Safety Agent/API responses; graph now consumes outcome and stays side-effect-free. Preserved current alert persistence. | [`backend/app/decision_engine.py`](../backend/app/decision_engine.py); [`backend/app/safety_agent.py`](../backend/app/safety_agent.py); [`backend/app/safety_graph.py`](../backend/app/safety_graph.py); [`backend/app/main.py`](../backend/app/main.py); focused tests; [`docs/safety-graph.md`](./safety-graph.md); this log. | Focused decision/agent/graph/experimental/image tests: 63 passed; full backend suite: 132 tests, 2 skipped. | Shared policy integrated; no migration or persistence change. | Band-to-notification mapping is provisional; persisted alert rows still represent every supported violation and may disagree with `safety_decision`. | Mentor confirmation, then Phase 2 persistence reconciliation and frontend semantics. |

| 2026-11-04 | Milestone 2 Phase 2 alert policy/persistence reconciliation | Gated new actionable alerts on shared overall/per-finding decisions; retained warning/pending/no-alert outcomes in existing metadata and history; guarded manual creation while preserving historical rows and lifecycle. | [`backend/app/persistence.py`](../backend/app/persistence.py); [`backend/app/main.py`](../backend/app/main.py); [`backend/tests/test_alert_policy_persistence.py`](../backend/tests/test_alert_policy_persistence.py); [`backend/tests/test_persistence.py`](../backend/tests/test_persistence.py); [`backend/tests/test_alert_api.py`](../backend/tests/test_alert_api.py); [`PROJECT_HANDOVER_CONTEXT.md`](../PROJECT_HANDOVER_CONTEXT.md); this log. | Focused suite: 78 passed; full backend suite: 143 run, 2 skipped (requires `TEST_DATABASE_URL`); no failures. `git diff --check` passed. | New alert creation matches provisional shared policy without schema migration; analytics still counts hazards without alerts. | Mentor policy approval, live PostgreSQL verification, frontend four-outcome display, delivery, image deduplication and historical recurrence remain open. | Phase 3 exact duplicate-image protection, after policy review and live DB verification planning. |
| 2026-11-05 | Milestone 2 Phase 3 exact duplicate-image protection | SHA-256 fingerprinted validated original uploads; guarded explicit observation-ID retries before inference; moved image storage after PK flush; returned deterministic structured 409 for confirmed exact retries. | [`backend/app/main.py`](../backend/app/main.py); [`backend/tests/test_exact_image_duplicates.py`](../backend/tests/test_exact_image_duplicates.py); [`PROJECT_HANDOVER_CONTEXT.md`](../PROJECT_HANDOVER_CONTEXT.md); this log. | Focused suite: 68 passed; full backend suite: 150 run, 2 skipped (`TEST_DATABASE_URL` unset); no failures. | Same-ID exact retries leave persisted records, alerts and analytics unchanged without a schema migration. | Generated-ID uploads and distinct-ID submissions cannot be deduplicated without a reliable inspection/submission scope; live PostgreSQL concurrency remains unverified. | Obtain a durable context contract, verify on disposable PostgreSQL, and plan Phase 4 recurrence separately. |
| 2026-11-05 | Milestone 2 Phase 4 historical PPE-violation recurrence analytics | Added read-only, named-work-area and canonical-hazard grouping from distinct persisted observation IDs, optional half-open `observed_at` bounds, lineage and deterministic rankings; kept existing hazard-row zone metrics and scoring/alert policy unchanged. | [`backend/app/analytics.py`](../backend/app/analytics.py); [`backend/app/main.py`](../backend/app/main.py); [`backend/tests/test_recurrence_analytics.py`](../backend/tests/test_recurrence_analytics.py); [`backend/tests/test_exact_image_duplicates.py`](../backend/tests/test_exact_image_duplicates.py); [`PROJECT_HANDOVER_CONTEXT.md`](../PROJECT_HANDOVER_CONTEXT.md); this log. | Focused suite: 37 passed; full backend suite: 165 run, 2 skipped (`TEST_DATABASE_URL` unset); no failures. `git diff --check` passed. | Informational recurrence endpoint implemented without schema or persistence changes. | Free-text areas do not prove site/zone identity; no worker or accident outcomes; live PostgreSQL unverified. | Verify with disposable PostgreSQL, seek mentor notification-policy review, and plan any first-class context model separately. |
| 2026-11-05 | Milestone 2 Phase 5A frontend safety semantics | Added one decision display for standard and experimental results, corrected no-finding/compliance wording, and exposed stored decisions in observation details when present. | [`SafetyDecisionPanel.tsx`](../frontend/src/components/SafetyDecisionPanel.tsx); [`AssessmentResults.tsx`](../frontend/src/components/AssessmentResults.tsx); [`ExperimentalSafetyViewer.tsx`](../frontend/src/components/ExperimentalSafetyViewer.tsx); [`ObservationHistory.tsx`](../frontend/src/components/ObservationHistory.tsx); [`ImageUploader.tsx`](../frontend/src/components/ImageUploader.tsx); [`types/index.ts`](../frontend/src/types/index.ts); this log; [`PROJECT_HANDOVER_CONTEXT.md`](../PROJECT_HANDOVER_CONTEXT.md). | `npm.cmd run build` passed with `tsc -b`; `npm.cmd run lint` exited 0 with six existing warnings; `git diff --check` passed. No component test runner exists. | Four backend decision outcomes are visible without changing backend policy or stateless experimental behavior. | Historical rows without decision metadata cannot show an outcome; recurrence frontend and PostgreSQL end-to-end verification remain. | Phase 5B disposable PostgreSQL verification. |
| 2026-11-05 | Milestone 2 Phase 5B-2 disposable PostgreSQL and connected verification | Created isolated integration/demo databases; exercised migrations, Admin/bootstrap/signup/RBAC, real-image and deterministic JSON assessments, alert lifecycle, analytics, recurrence, same-ID duplicate retry, stateless experimental inference, and connected browser views. | `safesite_integration_test` (application tables removed by test teardown); `safesite_demo` (left intact); this log; [`PROJECT_HANDOVER_CONTEXT.md`](../PROJECT_HANDOVER_CONTEXT.md). | PostgreSQL integration module 2/2 passed; demo migration head `0002_user_accounts`; direct SQL/API/browser observations documented above; `git diff --check` passed. | Major connected paths verified with disposable PostgreSQL, no application behavior change. | Per-hazard confidence attribution defect on multi-class images; no dismissal timestamp; live concurrency not tested; model and policy limits remain. | Correct confidence attribution, prepare reusable demo access/cases, and seek mentor policy review. |
| 2026-11-05 | Milestone 2 Phase 6A correctness and audit hardening | Corrected per-canonical-hazard image confidence/evidence, added nullable dismissal timestamp through migration and API, enforced eight-character password creation in backend/frontend while retaining legacy login. | [`main.py`](../backend/app/main.py); [`db_models.py`](../backend/app/db_models.py); [`persistence.py`](../backend/app/persistence.py); [`auth.py`](../backend/app/auth.py); [`bootstrap_admin.py`](../backend/app/bootstrap_admin.py); [`0003_alert_dismissed_at.py`](../alembic/versions/0003_alert_dismissed_at.py); [`AuthPages.tsx`](../frontend/src/auth/AuthPages.tsx); [`types/index.ts`](../frontend/src/types/index.ts); focused and PostgreSQL tests; this log and handover. | Focused 55/55; full backend 172 with 3 PostgreSQL skips; disposable PostgreSQL 3/3 and migration preservation check; frontend build/TypeScript pass, lint exit 0 with six existing warnings; `git diff --check` pass. | Phase 5B confidence defect fixed for new records and verified through live PostgreSQL persistence. | Preserved demo database needs forward migration; historical confidence/dismissal timestamps are not backfilled; model/policy and pending-completion limits remain. | Phase 6B pending risk assessment completion. |
| 2026-11-05 | Milestone 2 Phase 6B pending risk assessment completion | Added Safety Officer/Admin-only completion of existing pending assessment rows, shared scoring/decision recalculation, context/audit metadata, policy-gated alert creation, and a history-based frontend form. Forward-upgraded the preserved demo database after disposable verification. | [`persistence.py`](../backend/app/persistence.py); [`main.py`](../backend/app/main.py); [`test_auth.py`](../backend/tests/test_auth.py); [`test_database_integration.py`](../backend/tests/test_database_integration.py); [`client.ts`](../frontend/src/api/client.ts); [`types/index.ts`](../frontend/src/types/index.ts); [`PendingAssessmentCompletion.tsx`](../frontend/src/components/PendingAssessmentCompletion.tsx); [`ObservationHistory.tsx`](../frontend/src/components/ObservationHistory.tsx); [`AssessmentResults.tsx`](../frontend/src/components/AssessmentResults.tsx); [`App.tsx`](../frontend/src/App.tsx); this log and handover. | Focused auth 12/12, disposable PostgreSQL 9/9, full backend 179 with nine PostgreSQL skips, frontend build/TypeScript pass, lint exit 0 with six existing warnings, `git diff --check` pass. | Pending records can be completed without image re-upload; new alerts follow the unchanged provisional shared policy. Demo DB at head `0003_alert_dismissed_at` with all prior counts preserved. | No component tests or connected browser completion check; manual-alert concurrency not exercised; model/policy limitations remain. | Phase 6C production AI Safety Analysis integration. |
| 2026-11-06 | Milestone 2 Phase 6C production AI Safety Analysis | Routed primary AI Analysis to the persisted image endpoint, reused the existing upload/result/decision/completion components, moved incident view to history, linked saved Observation and policy-created Alerts, and removed the experimental viewer from normal routing. | [`App.tsx`](../frontend/src/App.tsx); [`client.ts`](../frontend/src/api/client.ts); [`ImageUploader.tsx`](../frontend/src/components/ImageUploader.tsx); [`AssessmentResults.tsx`](../frontend/src/components/AssessmentResults.tsx); this log and handover. | Connected browser and direct PostgreSQL verification described above; frontend build/TypeScript, lint and `git diff --check` passed. | Main image analysis is persisted; `safesite_demo` remains at `0003_alert_dismissed_at`. | No component harness, model accuracy certification, approved threshold or notification delivery. | Phase 6D recurrence analytics UI. |
| 2026-11-06 | Milestone 2 Phase 6D recurrence analytics UI | Added typed recurrence API client, dedicated navigation/page, summary cards, ranked recurring areas, canonical hazard groups, observation IDs and optional half-open time filter. | [`RecurrenceAnalyticsPage.tsx`](../frontend/src/components/RecurrenceAnalyticsPage.tsx); [`AppShell.tsx`](../frontend/src/components/AppShell.tsx); [`App.tsx`](../frontend/src/App.tsx); [`client.ts`](../frontend/src/api/client.ts); [`types/index.ts`](../frontend/src/types/index.ts); this log and handover. | Connected browser checks and preserved PostgreSQL identity described above; frontend build/TypeScript, lint, and `git diff --check` passed. | Existing recurrence endpoint is visible without changing backend recurrence or zone metrics. | Free-text areas, no worker/site identity, no specific-observation deep link, no component harness, provisional policy/model limits. | Phase 6E branding, demo accounts and final UI polish. |
| 2026-11-06 | Milestone 2 Phase 6E branding and mentor demo | Added shared mark/favicon, local demo bootstrap and launch helper, dev-only login hint, navigation/wording polish, visible alert lifecycle timestamps, and mentor checklist. | [`BrandLockup.tsx`](../frontend/src/components/BrandLockup.tsx); [`favicon.svg`](../frontend/public/favicon.svg); [`bootstrap_demo_accounts.py`](../backend/app/bootstrap_demo_accounts.py); [`test_demo_bootstrap.py`](../backend/tests/test_demo_bootstrap.py); [`start_demo_backend.ps1`](../scripts/start_demo_backend.ps1); [local demo guide](./local-mentor-demo.md); auth and dashboard components; this log and handover. | Focused bootstrap/auth 15/15; connected browser and direct demo PostgreSQL checks above; frontend build/TypeScript, lint, and `git diff --check` passed. | Three stable demo identities and preserved history are ready for a local mentor walkthrough. | No notification delivery, approved alert policy, model accuracy certification, first-class site/zone or worker identity; no component harness. | Rehearse the local checklist and seek mentor policy review. |
| 2026-11-06 | Normal local application environment | Created `safesite_local` fresh, migrated to head, bootstrapped three `.local` accounts, removed normal-UI demo hint, added explicit local scripts and README/setup instructions, then submitted one real image through the browser. | [`bootstrap_local_accounts.py`](../backend/app/bootstrap_local_accounts.py); [`test_local_bootstrap.py`](../backend/tests/test_local_bootstrap.py); [`migrate_local_database.ps1`](../scripts/migrate_local_database.ps1); [`start_local_backend.ps1`](../scripts/start_local_backend.ps1); [local setup](./local-setup.md); [`README.md`](../README.md); frontend wording; this log and handover. | Initial SQL counts 0/0/0/0; final 1 Observation/1 hazard/1 pending assessment/0 Alerts; bootstrap rerun 0 created/3 matched; 3 focused tests passed; connected browser, frontend build/TypeScript and lint passed; `git diff --check` passed. | Normal application now uses actual local submissions; `safesite_demo` remains intact as fallback. | Shared image-file directory is keyed only by Observation ID; notification policy, model and identity limitations remain. | Continue operator-led local image testing and separately review policy/model gaps. |

## Phase 2D Stage 1 outcome

- Exact model/YAML classes and supported violation mappings were recorded. The application risk taxonomy accepts a normalized `no_gloves` value, but the current checkpoint has no `NO-Gloves` class and the detector's explicit class-name mapping does not map one.
- Original matched data has 5,570 instances across 717 images; the 52 empty label files are retained and counted, and no malformed rows were observed in the focused class audit. Supplementary matched data has 11,521 instances across 1,416 images; the 10 orphan files/93 rows were excluded.
- A deterministic sample of 39 images (21 original, 18 supplementary) covers target classes across train, validation, and test. The supplementary `no_gloves` examples in the current sample are out of construction scope; this remains a concern about the sample and does not invalidate every annotation.
- Test/validation model weaknesses remain as previously measured. This audit does not claim causes beyond measured support, sampled visual scope, and reported evaluation metrics.
- **Stage 1 outcome:** audit complete; PPE remediation is not complete. **Stage 2 next steps:** resolve human policy/data decisions, licensing/provenance, duplicate scene groups, and orphan associations; then prepare a reviewed remediation manifest. No class is approved for bulk training by name alone.

## Phase 2D Stage 2 outcome

- **Scope:** source-selection and remediation planning only. No download, merge, relabeling, split creation, model training, or production change was performed. Stage 2 remains open until source suitability and licensing/provenance are reviewed.
- The decision register records 13 near-duplicate scene-family pairs. Nine supplementary train images overlap the scene family of the frozen original test image; four other pairs connect supplementary and original train/validation data. All 13 are marked quarantine in a future candidate manifest pending human source-group/split review. The original test remains untouched.
- Ten orphan label files (93 rows) have filename-family image candidates but no verified associations. They remain excluded from matched statistics and unresolved; filename matching alone is not accepted.
- The supplementary set contains 556 matched-image `no_gloves` boxes. Six earlier sampled examples were out of clear construction context, and the Stage 1 sample raised further concerns. This is a limited sample, not evidence that all 556 annotations are invalid. Human review must establish visible hands and task/site glove requirements. `none` has 797 matched boxes but no verified definition and is excluded from violation mappings.
- Primary-source research identified the Mendeley Dataset of PPE as a lead for explicit NoHelmet/NoVest; CPPED as a request-only, CC BY-NC lead for no gloves; and a TechScience paper describing multiple violation classes without a verified licensed data release. SH17/SHEL5K/SHWD/SFCHD are limited positive-PPE or helmet leads. Image-level rights, codebooks, access, and source lineage remain open. No source is approved for integration.
- The 26-class matrix preserves existing IDs 0–24 and lists NO-Gloves as proposed ID 25, conditional only. This does not authorize production mapping or experimental training.
- **Stage 2 outcome:** planning/research artifacts prepared; not complete. No annotations or source files were changed. Stage 3 remains unauthorized pending human annotation and source/license decisions.
- **Next steps:** obtain source-owner access, codebooks and image-rights clarification; review candidate samples and duplicate scene groups; resolve orphan associations or exclude them; approve any candidate class mapping and independent split plan before proposing Stage 3.

Detailed records: [supplementary review decisions](../reports/model-evaluation/phase-2d-supplementary-review-decisions.md), [dataset source research](../reports/model-evaluation/phase-2d-dataset-source-research.md), [class coverage matrix](../reports/model-evaluation/phase-2d-class-coverage-matrix.csv), [remediation plan](../reports/model-evaluation/phase-2d-remediation-plan.md).

## Maintenance protocol

Whenever a meaningful Milestone 2 task is completed:

1. Update the current snapshot.
2. Update the relevant requirement status.
3. Append an activity-log entry with the date.
4. Record artifacts and test evidence.
5. Record changed decisions and unresolved risks.
6. Update the next planned task.
7. Never erase historical entries; correct them transparently if necessary.

Keep this log concise and link to detailed reports using repository-relative paths. Do not mark work `Tested` without recording the test/evaluation evidence and outcome. Do not imply that the platform is certified, prevents accidents, or replaces professional inspection.

## Phase 8 preservation ? 2026-11-08

Removed embedded local/demo bootstrap passwords in favor of private environment
configuration, retained account/startup behavior, expanded Windows README and
recorded the [baseline](milestone-2-baseline.md) and
[security review](phase-8-preservation-report.md). Full backend suite passed in
`.venv-yolo` (199 run, nine skipped); ten focused bootstrap tests passed; frontend
build passed and lint retained six warnings. No local data or scoring policy
changed. Future redesign work belongs on the separate revamp branch.

## Phase 8.1A assessment usability — 2026-11-09

Initial verification: `revamp/milestone-2`, clean working tree. Baseline branch
and tag untouched; no staging, commit, push, reset, stash, rebase or merge.

- Added authenticated `/observation-query`: exact work area/ID, timezone-aware
  half-open date range, stable sort, pagination and backend counts across the
  complete filtered set. Risk/Pending match any current hazard assessment;
  mixed-risk observations retain all siblings. Facet counts ignore risk/page.
- Added assessment detail/context/audit lookup and Officer/Admin context PATCH.
  People exposed, duration and scoring repetition are assessment-specific
  operator context. Existing scoring, severity, bands and shared policy are
  reused; evidence and sibling scores remain intact.
- Observation locking, expected revision, same-context no-op and transactional
  rollback protect corrections. Manual alert creation shares the lock. Existing
  metadata holds context/audits; no database migration or new audit subsystem.
- Existing alerts retain lifecycle, risk and pre-correction snapshots. APIs/UI
  explicitly distinguish current risk and review-required history. Newly eligible
  alerts follow policy/deduplication; pending siblings still defer creation.
  Review flags have no automatic clear/reopen behavior in this phase.
- Added typed frontend clients, minimal editor/audit display, alert review notice,
  and target observation/assessment hash links. Existing links remain compatible.
  Filter context is retained for the later UI. No visual redesign.
- Validation: full backend **209 run, 200 passed, nine PostgreSQL skips**; eight
  focused tests pass on isolated SQLite ORM data. Coverage includes all risk
  bands, mixed/Pending counts, latest versions, dates/area, sort/page, lookup,
  valid/invalid edits, RBAC/authentication, recalculation, stale/no-op retries,
  sibling isolation, audit, alert preservation/deduplication and rollback.
  Frontend build/typecheck pass; lint exits 0 with six pre-existing warnings.
  `git diff --check` passes with line-ending notices only. The suite emitted
  nonfatal asset-network warnings and an existing Alembic deprecation warning.
  Database errors now log exception class rather than connection/error contents.
- Limits: full-filter aggregation is in memory; SQLite cannot validate PostgreSQL
  row-lock concurrency. No connected-browser check, review-clear workflow, or
  login deep-link restoration. Local/demo databases were not integration targets.

Exact request/response structures, filter semantics, metadata keys, reconciliation
rules and Antigravity guidance: [Phase 8.1A contract](phase-8-1a-assessment-contracts.md).

## Phase 8.1C partial verification — 2026-11-09

The user reports 25 observations, thumbnails, risk counts and pagination after
the proxy fix. The shared integrated browser remains at login and redirects
`#incidents` back to login. Connected verification is pending access to the
authenticated page; [the matrix](phase-8-1c-verification.md) separates isolated
test results, user-reported evidence and outstanding live checks.

58 focused backend tests passed with application database URLs disabled. Added
isolated repeated-correction coverage across all alert lifecycle states, including
original snapshots, audit growth, stale requests and duplicate prevention.
Build/typecheck passed; lint passed with seven existing warnings; diff check
passed. No production code or saved records/images changed, no Git mutations,
and no 8.1D work. Phase 8.1C is incomplete; combined A/B/C checkpoint readiness
is not yet verified. Next: authenticate/share the integrated browser and complete
the read-only live checks.

## Phase 8.1C resumed connected results — 2026-11-09

Supersedes the authentication blocker above. Signed-in read-only verification is
complete: all risk tabs, exact ID search, Zone A–D filters, date range, ordering,
page sizes/next/previous, row expansion, original/overlay previews, valid off-page
assessment deep link, sidebar controls on all seven pages and sampled responsive
geometry were exercised. Counts: 25 observations, 44 completed assessments,
Pending 0; 13 alerts (6 open, 5 resolved, 1 dismissed, 1 acknowledged). Complete
observation/assessment metadata and alert GET responses matched before/after.

Four confirmed defects remain unchanged in this read-only run: image dialog
focus/Escape, mobile closed-menu off-screen keyboard focus/Escape, silent invalid
assessment links, and pinned observation left behind when clearing a deep link
(21 rows at page size 20). Non-empty Pending and review-required alert displays
cannot be exercised with existing records; isolated tests cover their behavior.

58 focused tests rerun successfully; frontend build/typecheck passes, lint exits
0 with seven existing warnings, diff check passes. No saved data, images, source
implementation or Git state mutations; no 8.1D. Verification is complete with
findings; fix/recheck these defects before a clean checkpoint. See the
[final verification matrix](phase-8-1c-verification.md).

### Phase 8.1C four-defect corrections — 2026-11-09

Implemented image-dialog and mobile-navigation keyboard focus containment,
Escape/restoration and inert backgrounds. Added deep-link assessment membership
validation and return-to-history; cleared supplemental state on hash changes with
stale-response protection. Off-page linked details are separated from backend
pagination, avoiding duplicate rows or a 21-row page. Historical targets display
their exact assessment without historical edit controls.

58 isolated backend tests and frontend build/typecheck pass; lint passes with
seven existing warnings and `git diff --check` passes. Post-fix connected
verification remains pending because the shared browser is signed out; sign-in
was requested. Earlier connected successes must not be treated as post-fix
results. A verified A/B/C checkpoint is not yet recommended. All existing work
preserved; no saved records, scoring, alerts, schema or Git history modified.

### Phase 8.1C final authenticated sign-off — 2026-11-09

All four post-fix browser checks passed. Original/annotated modal focus,
Escape/trapping/restoration; mobile/tablet inert navigation and focus lifecycle;
valid/missing/mismatched deep links; supplemental-state cleanup and Back/Forward;
pagination limits/uniqueness; all risk tabs, thumbnails and desktop sidebar were
verified. Current baseline: 26 observations, one Pending assessment, 13 alerts.
Full observation-query and alert responses matched before/after testing.

No implementation regression required a change. Only verification documentation
changed in this pass; prior build/typecheck, lint and 58 isolated backend test
results remain applicable. Diff whitespace check rerun. Combined A/B/C is ready
for a Git checkpoint with the limitations in the [final matrix](phase-8-1c-verification.md).
Nothing staged or committed; no saved data changes or Phase 8.1D work.

### Phase 8.1 Multi-Pending assessment follow-up

Kept persisted analysis results/evidence mounted after the first completion;
added confirmed-response retention, next-form focus, completion progress, final
decision gating, refresh recovery by persisted observation ID, and immediate
duplicate-submission guards. History completion refresh is now background-only.
Recorded-context conflict rules and existing correction workflow are unchanged.

59 isolated backend tests pass, including a new two-Pending score/recovery/audit/
duplicate regression. An intercepted browser fixture verified sequential forms,
draft/evidence retention, reload and double-submit prevention. Connected checks
were read-only: reference #50 remains High (60), #51 remains Pending; 26
observations and 13 alerts match before/after. Build/typecheck and lint pass with
seven existing warnings. See the [verification details](phase-8-1c-verification.md).
No scoring/alert policy change, live writes, Phase 8.1D, staging or commits.

### Phase 8.1 Git checkpoint validation — 2026-11-09

User authorized staging, commit and normal push of Phase 8.1A/B/C and
Multi-Pending on `revamp/milestone-2` to its existing origin upstream.
59 isolated backend tests rerun successfully with both database URL variables
empty; frontend build/TypeScript and lint pass (seven known warnings).
Whitespace checks pass. Reviewed the 24 intended source/test/documentation files
and scanned them for private keys, token patterns, literal secrets and credential
URLs; no matches. No environment files, databases, evidence, weights, datasets,
generated reports or caches are included. Preserved baseline branch remains
`66a49ef91b8b46ae450cb307b4f0089706c2804e`; stable tag object remains
`94677ccc21684aab26d078037e2bd0bd06dc917a` (same peeled baseline commit).
No production writes, detector runs, Phase 8.1D or Phase 8.2 work in this checkpoint.
Earlier connected verification and its documented coverage limits still apply.

### Phase 8.1D overall observation risk aggregation — 2026-11-13

Added a derived overall summary to observation detail and query items. For each
finding the latest assessment version is considered; only valid completed
scores (1–100) participate, and the overall score is their maximum, classified
with the existing risk-band policy. No scoring formula, thresholds, alert
policy, assessment history, or database schema changed. Pending and incomplete
findings make a valid maximum provisional; all-Pending, malformed/missing, and
no-supported-finding states return null scores with explicit statuses. Existing
risk filters/facets remain per-finding existential filters. The collapsed
Safety Incidents card now presents one overall risk badge, while expanded
findings retain individual bands and the safety decision stays separate.

Automated verification: full isolated backend discovery ran 213 tests successfully;
nine PostgreSQL integration tests were skipped because `TEST_DATABASE_URL` was
unset to prevent access to any saved database. Frontend TypeScript/Vite
production build passes. Lint exits successfully with seven existing warnings.
`git diff --check` passes (line-ending notices only). At this point the
integrated browser had not attached, so live saved-observation rendering and
before/after observation/alert comparisons were pending. Tests used
isolated data and no local/demo records were modified. No Phase 8.2 work,
staging, or commit was performed.

Intermediate browser attempt (superseded by the final sign-off below): the shared integrated browser still
reported `http://127.0.0.1:5173/#login` and rendered the sign-in form despite
the user reporting a successful sign-in. Per instruction, no further browser
refresh/re-authentication or server restart was attempted. No authenticated
observation/alert snapshots were captured, so live-card behavior and before/
after data equality remain unverified. No application data requests or writes
were made during this blocked attempt; connected sign-off was pending then.

Final connected Phase 8.1D sign-off — 2026-11-13: the shared browser was
authenticated at `http://127.0.0.1:5173`; `localhost:5173` was unauthenticated
and redirected to login, so verification stayed on the authenticated 127.0.0.1
origin. Read-only observation and alert GET snapshots returned 27 observations
and 13 alerts before and after verification. The same canonical projection
digest was `20ee15da920d35ef6b848612ba8e0371c57deb1121658e55ba9c7f781a345c3f`;
alert statuses remained 5 open, 1 acknowledged, 5 resolved, and 2 dismissed.
Reference `img-obs-1852c096` remained High 60, provisional, with 1 Pending:
assessment #50 was completed High 60 and #51 remained Pending. Cards displayed
one overall risk badge, separate decision, and expanded individual findings.
All risk tabs were checked: All 27, Pending 1, Critical 2, High 11, Moderate
16, Low 13. The interface clearly states that tabs match individual findings;
the mixed-risk High-45 observation appeared in High, Moderate, and Low. Original
and annotated evidence loaded (2752×1536); no-supported-finding cards carried
the explicit disclaimer that this does not establish the site is safe.
Mobile navigation opened as a dialog and Escape restored focus to its trigger.
Mobile/tablet/desktop widths had no horizontal overflow. No all-Pending
observation exists in the current local data, so that state remains verified
only by isolated tests. No user data was modified. Earlier 213-pass backend
validation, frontend build, lint, and whitespace results remain applicable;
this browser-only sign-off changed documentation only. Phase 8.1D is ready for
Git sign-off, with live all-Pending presentation as the noted data-availability
limitation. No Phase 8.2 work or commit was performed.

### Phase 8.2A observation-level safety cases — 2026-11-13

Audited the existing alert model and documented the grouping/data contract
before implementing API changes. Safety cases are a read-time group of all
persisted alerts sharing `observation_id`; the stable key is
`observation:<observation_id>`. No safety-case table or migration is added.
Cases only exist for observations with at least one alert. Existing alert rows,
assessment versions, snapshots, evidence, statuses, timestamps, and corrections
remain the source of truth.

Added authenticated `GET /safety-cases` and `GET /safety-cases/{observation_id}`.
The list filters on exact work area, derived case status, half-open timezone-aware
observation dates, observation/case ID search, stable newest/oldest sorting, and
case-level pagination. `total_cases` counts unique observations and
`total_alerts` counts their individual child alerts before pagination. Case
detail includes Phase 8.1D's existing overall summary, original/annotated
availability flags, individual alert details, full detected finding assessment
history, and existing correction audit metadata. Alert correction review markers
remain attached to the original alert.

Case state is conservative: any Open child means Open; absent Open, any
Acknowledged means Acknowledged; all Resolved means Resolved; all Dismissed
means Dismissed; mixed Resolved/Dismissed becomes `mixed_closed`. Unresolved
count includes only Open and Acknowledged. No case-level lifecycle action was
added; the existing Safety Officer/Admin per-alert API remains unchanged.
Typed `SafetyCaseResponse`, list/filter contracts, and API client fetch helpers
are ready for Phase 8.2B; no Alert Register UI redesign was made.

Full isolated backend discovery: 219 tests passed, nine PostgreSQL integration
tests skipped with `TEST_DATABASE_URL` unset. Frontend TypeScript/Vite build
passed; lint passed with seven existing warnings; `git diff --check` passed.
Case tests cover unique grouping, mixed lifecycle states, filtering/search,
pagination/counts, correction review lineage, authenticated reads, and
no-write behavior. No local/demo database or image evidence was used or changed.
No schema migration, scoring/decision change, alert mutation, staging, or commit
was performed. The first list implementation eagerly loads related graphs to
avoid N+1 queries but groups candidates in application memory; SQL aggregation
is a scale optimization if alert volume grows substantially.

### Phase 8.2C safety case integration audit — 2026-11-13

The Alert Register was still rendering the pre-case one-row-per-alert interface;
the case endpoints had no consumer, and the safety-case cards, filters, detail
drawer, row, summary, and hook reported by the design handoff were absent. Added
the safety-case workspace to the existing `#alerts` route, wired list/detail
queries, backend filters and counts, evidence, assessment/correction details,
individual child lifecycle actions, and `#incidents` deep links. Added a missing
Vite `/safety-cases` proxy and non-JSON/invalid-JSON API errors. No case bulk
action is present.

The authenticated browser connected to the existing backend and read-only
before/after snapshots matched exactly: 27 observations and 13 alerts (IDs 3–15;
5 Open, 1 Acknowledged, 5 Resolved, 2 Dismissed). The checked-out API source
contains case routes, but the live server's OpenAPI omits them and its case GET
returns 404. The server was not restarted; populated case/drawer verification is
therefore blocked on loading the current workspace backend. Empty/error-page
layout showed no horizontal overflow at 390, 768, and 1280 pixels. A later
read-only snapshot retry returned 401 after the integrated browser session
expired; the session was not reauthenticated.

Full isolated backend suite: 219 passed, 9 PostgreSQL integration tests skipped.
Frontend build passed; lint passed with six existing warnings; no frontend test
script is configured; `git diff --check` passed. No database records, alert
statuses, images, models, or baseline refs were changed. Phase 8.2A/B/C requires
connected populated-case verification before Git checkpoint sign-off; no staging
or commit was performed.

### Phase 8.2C runtime resolution and final verification — 2026-11-13

Resolved the Alert Register runtime mismatch. Port 8000 was held by a stale
SafeSite backend process from this workspace whose loaded OpenAPI omitted the
two safety-case routes. After confirming its process command, executable and
owner, stopped only that SafeSite process and started the current workspace
backend with `scripts/start_local_backend.ps1`. The script targets
`safesite_local` through its local-only URL helper and does not bootstrap
accounts or run migrations. Health returned 200, OpenAPI listed both case
routes, unauthenticated case reads returned 401, and authenticated list/detail
reads returned JSON.

Authenticated read-only before/after snapshots matched exactly: 27 observation
IDs, 13 alert IDs and timestamps/statuses, and complete case assessment-history
summaries. The API returned 10 unique cases and 13 individual alerts. The
Alert Register grouped multi-alert observations, preserved all child alert
history, and separated overall risk from derived case status. Search,
work-area, status, date, sorting, case-level pagination, thumbnails, original
and annotated evidence, assessment history and Safety Incidents deep links
were verified. The case drawer and image modal passed Escape/focus restoration
and focus containment checks; 390/768/1280px layouts had no horizontal
overflow. No live alert lifecycle action was taken. Current data has no
review-required alert or mixed-closed case to demonstrate live, though isolated
tests cover these states.

Focused isolated backend regression subset passed 43 tests; the full previously
validated backend suite remains 219 passed / 9 PostgreSQL integration tests
skipped. Frontend build passed, lint passed with six existing warnings, and
`git diff --check` passed. No local records, images, weights, schema, or
baseline refs changed. Phase 8.2A/B/C is ready for sign-off; no staging or
commit was performed.

### Phase 8.2D final quality audit — 2026-11-14

Audited the authenticated Alert Register and complete safety-case
implementation on `revamp/milestone-2`. Current connected data shows 10 unique
cases and 13 individual alerts, with overall observation risk separate from
case lifecycle status and unresolved counts. Mixed child states retain the
conservative summary (Acknowledged plus Dismissed remains Acknowledged with
one unresolved alert; resolved plus dismissed is `mixed_closed`). Individual
status controls target persisted alert IDs, list/detail refresh after success,
and no bulk case action is present. No connected lifecycle mutation was made.

No additional confirmed defect required a code change. Full isolated backend
suite: 219 passed, 9 PostgreSQL integration tests skipped because no test DB
URL is configured. Frontend TypeScript/Vite build passed; lint passed with six
existing warnings outside the new Safety Case components; no frontend test
script is configured; `git diff --check` passed. Existing live observations,
assessments, alerts and evidence were not written during verification. Review
required and `mixed_closed` live examples remain unavailable, with isolated
tests covering those conditions. Phase 8.2A/B/C is ready for checkpoint
approval; Phase 8.2 can close after that checkpoint. Nothing was staged or
committed.

### Phase 8.3A Zone and Recurrence Analytics architecture audit — 2026-11-14

Audited the existing Zone Analytics and Recurrence Analytics services, APIs,
UI, persistence relationships and tests on `revamp/milestone-2` at checkpoint
`4833343a8228b55628fd4ad6ee7ee7adea1da99d`. Added
[`phase-8-3a-analytics-architecture.md`](phase-8-3a-analytics-architecture.md)
with current metric denominators, recurrence normalization/date semantics,
confirmed limitations, reusable contracts/components, additive API proposals,
and scoped plans/tests for Phases 8.3B, 8.3C and 8.3D.

No application code, schema, persisted data, evidence, risk policy, alerts,
models or Git history were changed. The browser was signed out, so no connected
live-data verification is claimed. No tests were run because this phase made
documentation-only changes; `git diff --check` was used as the documentation
validation. Phase 8.3B/C implementation has not started.

### Phase 8.3B evidence-linked Zone Analytics implementation — 2026-11-14

Implemented the additive timezone-aware `GET /analytics/zones?start=&end=` summary contract and authenticated paginated `GET /analytics/finding-observations` contract. Legacy zone metrics and their meanings remain intact. New explicit fields distinguish supported finding rows, distinct observations, valid latest assessments, Pending/incomplete latest assessments, Phase 8.1D overall risk distribution/provisional state, individual alert IDs/statuses, and unique observation safety-case counts. The common assessment helper classifies latest scores with the existing risk policy; it does not change scoring.

Replaced the summary-only Zone page with date controls, frequency-labelled work area comparisons, separate per-finding and observation risk summaries, metric units, category drill-down, paginated observation cards, thumbnails/evidence viewer, and Safety Incidents/case links. The existing Safety Case Register now opens `#alerts?observation_id=...` targets while preserving ordinary `#alerts`. Recurrence calculation and UI were not modified.

Focused zone/recurrence tests passed (24). Full isolated backend suite, frontend build/typecheck/lint and `git diff --check` results are to be recorded after final validation. The integrated browser was on the login page at `http://127.0.0.1:5173/#login`; populated connected UI checks were therefore unavailable and no server restart, authentication attempt, or data write was made. Existing `safesite_local`/`safesite_demo` records, images, alerts, assessments, risk policy, model weights and baseline references were not modified by this implementation.

#### Phase 8.3B final verification update — 2026-11-14

The final full isolated backend suite completed successfully: 226 tests passed and 9 PostgreSQL integration tests skipped because `TEST_DATABASE_URL` is not configured. Focused Zone/Recurrence tests passed (26). Frontend TypeScript/Vite build passed. Oxlint passed with five warnings in unchanged files (`App.tsx`, `AuthContext.tsx`, `OverviewPage.tsx`, and `ObservationHistory.tsx`); the new/changed Zone components and Alert Register integration introduced no lint warnings. No frontend test script is configured. `git diff --check` passed.

The integrated browser remains at `http://127.0.0.1:5173/#login`. Since it is signed out, the populated connected UI checks (metrics, date controls, drawer focus behavior, images, and responsive viewport review) remain unverified. No server was restarted and no sign-in attempt or live API/data mutation was made. Phase 8.3B is ready for authenticated integration review; connected sign-off remains outstanding.

#### Phase 8.3B connected verification attempt — 2026-11-14

The shared browser origin `http://127.0.0.1:5173` was at `#login`, so the authenticated page checks and read-only before/after data snapshots could not be completed. No sign-in attempt, server restart, or data mutation was made. Unauthenticated same-origin probes returned JSON through Vite's `/analytics` proxy: `/analytics/zones` returned 401 (route reached FastAPI) and `/analytics/finding-observations` returned 404. Live OpenAPI lists the old `/analytics/zones` operation without the new date parameters and omits the supporting-observation route, confirming a runtime/source mismatch. Browser proxy did not return HTML. Connected metric, evidence, navigation, responsive, accessibility, and preservation checks remain unverified; Phase 8.3B connected sign-off is pending a correctly loaded backend and authenticated browser.

#### Phase 8.3B backend reload and sign-off attempt — 2026-11-14

The identified stale backend process was confirmed to be this workspace's
SafeSite Uvicorn process and replaced using the approved local startup script.
The script targets safesite_local without migration, reset, seeding, or
bootstrap. Health returned 200; OpenAPI exposes both new analytics routes and
the zone start/end parameters. Unauthenticated requests through FastAPI and
the Vite proxy return 401 JSON. The shared browser page
4d12a393-54c1-4ff8-8fed-75d26552ccf3 remains at
http://127.0.0.1:5173/#login; no other authenticated browser page is shared.
Authenticated UI checks and before/after data snapshots were not taken.
Connected sign-off remains blocked; no saved data was modified.

#### Phase 8.3B shared browser status — 2026-11-14

The controlled page (ID 4d12a393-54c1-4ff8-8fed-75d26552ccf3) remains at
http://127.0.0.1:5173/#login and shows Login failed; recent browser requests
returned 502. No login retry, service restart, or data mutation was performed.
Authenticated UI checks and before/after observation/alert snapshots remain
unavailable, so connected sign-off is still pending. A manual Chrome checklist
is recorded in docs/phase-8-3b-zone-analytics.md.

#### Phase 8.3B final connected sign-off attempt - 2026-11-14

The integrated-browser page handle supplied for `http://127.0.0.1:5173` (`4d12a393-54c1-4ff8-8fed-75d26552ccf3`) was unavailable to the browser tool (`Page ... not found`). Opening the same origin in a new integrated-browser page also failed. Therefore the current page URL, authentication state, and login-request result could not be inspected; this attempt does not establish that login failed or that the authenticated browser is in a different context. No login was submitted, no service was restarted, and no credentials or tokens were accessed. Authenticated API snapshots and Zone Analytics UI checks could not be performed, so connected sign-off remains outstanding.

Manual read-only checklist: share the active authenticated tab at `http://127.0.0.1:5173` in the integrated browser (same host and port). Compare Zone Analytics totals with `GET /analytics/zones?start=<inclusive>&end=<exclusive>` and supporting-observation items/totals with `GET /analytics/finding-observations`. Check distinct-observation paging, date filters/Clear Filters, finding versus overall risk, Pending/provisional state, evidence previews, `#incidents` and `#alerts?observation_id=...` navigation, keyboard Escape/focus restoration, and 390px/768px/1280px layouts. Capture read-only observation/assessment-history and alert-status/timestamp snapshots before and after; do not submit assessment or alert actions.

### Phase 8.3C — Evidence-linked Recurrence Analytics — 2026-11-14

Upgraded Recurrence Analytics into an interactive area/category investigation workspace. The authoritative recurrence API and counting definition are unchanged: one group per supported canonical PPE hazard and trimmed named work area, with recurrence requiring at least two distinct observation IDs. Multiple detection rows within one observation and assessment versions do not add recurrence; placeholder areas remain excluded; date bounds remain observation-time, timezone-aware and half-open.

The page now presents the existing groups as searchable/sortable responsive combination cards, labels the distinct-observation unit, distinguishes repeated from once-observed pairs, and opens the Phase 8.3B shared paginated evidence drawer. Drawer queries use `area_mode=recurrence` and the exact selected area/category/time window. Observation risk is shown independently of frequency; assessment history, evidence previews, Safety Incidents and conditional Safety Case links reuse existing contracts/components. No backend contract or data was changed.

Focused Zone and Recurrence suites pass (27 tests total). The full isolated backend suite passed 227 tests; 9 PostgreSQL integration tests skipped because no disposable `TEST_DATABASE_URL` is configured. Frontend TypeScript/Vite build passed. Lint passed with five existing warnings in unchanged files; the updated recurrence component adds no warning. The integrated browser page supplied for this task displayed `chrome-error://chromewebdata/`, so connected UI, image, keyboard and responsive verification was not available. No login was attempted, no service was restarted, and no saved observations, assessments, alerts or evidence were modified. Combined Zone/Recurrence connected sign-off remains deferred to Phase 8.3D. See `docs/phase-8-3c-recurrence-analytics.md`.

#### Phase 8.3D final integration audit — 2026-11-14

Static contract review found Zone and Recurrence semantics consistent for supported hazard pairs, named-area normalization/exclusions, observation-time half-open date windows, and distinct-observation pagination. Focused tests passed (27); the full isolated backend suite passed 227 tests with 9 PostgreSQL tests skipped after clearing database connection variables. Frontend build and lint passed (five existing warnings); `git diff --check` passed. No confirmed application defect was found. The integrated browser returned `chrome-error://chromewebdata/`, and no listeners were present on ports 8000 or 5173, so live API comparison, UI checks, and authenticated before/after data snapshots could not be performed. No services were restarted and no saved data was intentionally changed. Phase 8.3 is an automated-verified checkpoint only; connected sign-off remains outstanding. See `docs/phase-8-3d-final-verification.md` and its manual Chrome checklist.
