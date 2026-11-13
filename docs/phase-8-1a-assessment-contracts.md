# Phase 8.1A — assessment contracts

Implemented on `revamp/milestone-2`, 2026-11-09. No schema migration, scoring
policy change, detector invocation, image rewrite, or visual redesign is involved.

## Ownership and compatibility

An Observation owns identity, capture time, source, work area, original submission
context and image metadata. A detected hazard owns model evidence/confidence.
Each RiskAssessment owns status and calculated scoring results. Effective context
is assessment-specific: `raw_metadata.assessment_contexts[assessment_id]`, then
legacy completion `resolved_context`, then observation defaults. Corrections freeze
existing sibling contexts and never change the observation defaults. These are
operator scoring inputs, not exact YOLO person counts or analytics recurrence.

Assessment IDs and versions remain stable during correction. `revision` is a
separate concurrency token, counting corrections plus a legacy completion if
present. Existing GET `/observations`, GET `/observations/{observation_id}`,
PATCH `/assessments/{assessment_id}/complete`, image and alert routes remain.
The legacy completion route still fills missing observation defaults, but honors
assessment-specific context and records its resolved context. Use the new context
endpoint for all new editing and pending-completion UI.

## Query contract

### Phase 8.1D observation-level risk summary

Both `GET /observation-query` items and `GET /observations/{observation_id}`
include a backend-derived summary. It does not replace or rewrite individual
assessment rows or history:

```ts
type OverallRiskSummary = {
  overall_risk_score: number | null;
  overall_risk_band: 'Low' | 'Moderate' | 'High' | 'Critical' | null;
  overall_risk_provisional: boolean;
  overall_risk_status: 'assessed' | 'provisional' | 'pending' | 'incomplete' | 'no_supported_findings';
  completed_assessment_count: number;
  pending_assessment_count: number;
  incomplete_assessment_count: number;
  total_assessed_findings: number;
};
```

For each detected finding, only its latest `assessment_version` is effective.
The overall score is the maximum valid score (1–100) among those latest
completed assessments; the band is derived through the existing `risk_band`
policy. Scores are never summed or averaged. `provisional` is true when a valid
maximum exists while at least one finding is Pending or incomplete. If every
finding is Pending, score and band are null and status is `pending`. Missing
assessment rows and malformed completed scores are counted as incomplete and
never treated as Pending or assigned an invented score. No findings yields
`no_supported_findings` and null score/band; it is not evidence that the site is
safe. Counts are finding counts, and `completed_assessment_count` counts latest
completed rows even when their score is malformed (such a row also increments
`incomplete_assessment_count`).

Risk query tabs and existing facets retain their original existential,
individual-finding semantics: e.g. High matches an observation with at least
one latest High finding, even if its overall maximum is Critical. The collapsed
Safety Incidents card shows only the overall maximum classification; expanded
details show per-finding risk. The summary is computed from persisted latest
assessment versions at read time, so corrections take effect without rewriting
prior assessment snapshots or adding duplicate derived columns.

Authenticated `GET /observation-query`:

| Parameter | Contract |
| --- | --- |
| `risk` | `All` (default), `Pending`, `Low`, `Moderate`, `High`, `Critical`; case-sensitive |
| `work_area` | Optional exact, case-sensitive stored work-area match |
| `start`, `end` | Optional timezone-bearing ISO timestamps; observation time in `[start,end)`; start must precede end |
| `observation_id` | Optional exact ID lookup, combined with other filters |
| `sort` | `newest` (default) or `oldest`; observed_at then observation_id in the same direction |
| `limit`, `offset` | Default 20/0; limit 1–100, offset >= 0 |

Response (`Counts` has all five keys, including zeros):

```ts
type Counts = { Pending: number; Low: number; Moderate: number; High: number; Critical: number };
type QueryResult = {
  items: (ObservationDetailResponse & { assessment_counts: Counts })[];
  total: number;
  limit: number;
  offset: number;
  assessment_counts: Counts;
  observation_counts: Counts;
  unfiltered_risk_total: number;
};
```

Only each hazard's highest `assessment_version` contributes to counts and risk
matching. A risk filter is existential: an observation matches if at least one
current assessment has that band/status. All its hazards/assessments remain in
the response, including nonmatching siblings. Pending is assessment status,
not the overall safety decision. Completed historical versions never inflate
counts. No-finding observations appear in All, but not in a risk band.

`total` counts matching observations after ALL filters, before pagination.
Top-level counts apply work-area/time/ID filters but intentionally ignore risk
and pagination, enabling stable filter facets. `observation_counts` counts
distinct observations separately for each band; mixed-risk observations can
contribute to multiple keys, so these counts must not be summed as a total.
`unfiltered_risk_total` counts observations before the risk filter.
Per-item `assessment_counts` includes every current assessment in that item.

## Lookup and correction contracts

Authenticated `GET /assessments/{assessment_id}` returns:

```ts
type Context = { people_count: number | null; duration_minutes: number | null; repeated_count: number | null };
type AssessmentState = {
  observation_id: string;
  detected_hazard_id: number;
  assessment_id: number;
  revision: number;
  context: Context;
  assessment: PersistedAssessmentResponse;
  safety_decision: SafetyDecisionResponse; // this finding, not the whole observation
  audit_history: AssessmentCorrectionAudit[];
  reconciliation: {
    review_required: boolean;
    alert_ids: number[];
    reason: string | null;
    state: 'review_required' | 'linked' | 'deferred_pending' | 'unchanged';
  };
};
```

`PATCH /assessments/{assessment_id}/context` requires Safety Officer or Admin and
all four fields below. Unknown fields, nulls, fractions, strings and booleans are
rejected. Integer minima retain the existing scoring validation.

```json
{
  "expected_revision": 0,
  "people_count": 4,
  "duration_minutes": 60,
  "repeated_count": 2
}
```

Minima: revision/repetition 0; people/duration 1. The response is `AssessmentState`.
GET before editing and send its revision. A stale revision or superseded
assessment returns 409 `{detail:{code,message}}`; reload and let the operator
review before resubmitting. A retry with the old revision has no effects. A
same-context request at the current revision is a no-op for a completed row.
Pending rows can be completed with this endpoint. Missing rows return 404,
invalid input 422, unauthenticated requests 401, unauthorized edits 403,
unconfigured database 503, database errors sanitized 500.

The observation row lock serializes corrections, legacy completions and manual
alert creation. The correction transaction includes scoring, metadata, audit and
any eligible alerts, with rollback on failure. The same SiteRiskAgent severity,
likelihood/exposure tables, product formula and risk bands apply; shared
`evaluate_safety_decision` controls both finding and observation decisions.
YOLO, original evidence, observation identity and sibling scores are untouched.

## Audit and alert reconciliation

Existing observation JSON metadata is reused; no parallel audit store or migration.
`assessment_corrections` is an append-only application audit list, filtered by
assessment ID in the lookup response. Each record contains:

```ts
type AssessmentCorrectionAudit = {
  assessment_id: number; revision: number;
  previous_values: Context;
  updated_values: { people_count: number; duration_minutes: number; repeated_count: number };
  previous_result: { status: string; risk_score: number | null; risk_band: string | null };
  updated_result: { status: 'completed'; risk_score: number; risk_band: string };
  previous_decision: SafetyDecisionResponse;
  updated_decision: SafetyDecisionResponse;
  previous_observation_decision: SafetyDecisionResponse | null;
  updated_observation_decision: SafetyDecisionResponse;
  changed_by_user_id: string; changed_at: string; // UTC ISO timestamp
};
```

Alert rows retain their IDs, assessment references, message, risk band, lifecycle
status and timestamps. Before first correction, linked alerts' assessment and
finding-decision snapshots are retained in `alert_correction_snapshots`. These
are the pre-correction snapshots, not a reconstruction of unknown historic data.
Every corrected finding with an existing alert is explicitly review-required,
even if the band is unchanged or the alert is already resolved/dismissed. Nothing
is automatically closed, reopened, dismissed or deleted.

Existing alert APIs now expose `review_required`, `reconciliation_reason` and
`current_assessment`. Their existing `assessment` and decision display fields use
the preserved pre-correction snapshot where available; `risk_band` remains the
original alert band. Render historical and current information distinctly.

A warning becoming alert-grade creates an alert only when the overall shared
policy also permits an alert. A pending sibling continues to defer creation.
Completing the final pending finding can create alerts for eligible siblings.
Creation checks existing hazard alerts under the same observation lock and uses
the existing unique deduplication key. Existing closed alerts are retained and
not duplicated. `alert_ids`/`state` are derived on lookup so later sibling
completion does not leave a stale deferred state in the API.

Review-required metadata intentionally remains until a future explicit review
workflow is designed. Existing lifecycle actions remain explicit operator
actions; they do not erase the correction review marker. No automated case
regrouping or notification delivery is introduced.

## Antigravity integration and navigation

Use [types](../frontend/src/types/index.ts) and
[client helpers](../frontend/src/api/client.ts): `queryObservations`,
`fetchAssessmentContext`, `correctAssessmentContext`, existing
`fetchObservationDetail` and `fetchAlerts`. Refresh query counts and the
observation after edits; use backend counts rather than the loaded page or the
overall decision to derive risk tabs. Choose the highest assessment_version per
hazard for the current card, retaining older rows as history.

Use [incidentLink](../frontend/src/utils/incidentNavigation.ts):

```text
#incidents?observation_id=<URL-encoded-ID>&assessment_id=123&risk=Pending&work_area=North
```

The existing hash router now parses the section before `?`. The incident page
loads the exact observation even outside its first page, expands it and focuses
`assessment-123`. A mismatched assessment/observation pair reports an error.
Legacy `#history`, `#incidents` and `#experimental` links remain valid. Filter
parameters are preserved in the hash for the later filter UI; the current minimal
UI does not apply those context parameters when showing a direct target. An
unauthenticated redirect currently does not restore the original deep link.

Minimal UI additions: context editor, inspectable correction history for managers,
submission-context labels, and an explicit alert review notice. The existing
pending-completion form remains compatible. No redesigned controls/cards/styles.

## Verification and limitations

### Phase 8.1D final regression status — 2026-11-13

This section records the isolated automated regression run. Its initial browser
attachment limitation was subsequently resolved; the final connected sign-off
is recorded below.

The full isolated backend suite ran 213 tests successfully; nine PostgreSQL
integration tests were skipped because `TEST_DATABASE_URL` was unset. Frontend
TypeScript/Vite build and lint passed; lint reports seven existing warnings.
`git diff --check` passed. At the time of this automated regression run, the
integrated browser had not yet attached and connected data comparison was
pending. No saved local/demo data was changed by the isolated run.

Changed files:

- Backend: [main.py](../backend/app/main.py), [persistence.py](../backend/app/persistence.py),
  [assessment_context.py](../backend/app/assessment_context.py), [assessment_queries.py](../backend/app/assessment_queries.py).
- Tests: [test_assessment_context.py](../backend/tests/test_assessment_context.py).
- Frontend: [App.tsx](../frontend/src/App.tsx), [client.ts](../frontend/src/api/client.ts),
  [types/index.ts](../frontend/src/types/index.ts), [ObservationHistory.tsx](../frontend/src/components/ObservationHistory.tsx),
  [AssessmentContextEditor.tsx](../frontend/src/components/AssessmentContextEditor.tsx),
  [AlertsPage.tsx](../frontend/src/components/AlertsPage.tsx), [incidentNavigation.ts](../frontend/src/utils/incidentNavigation.ts).
- Documentation: this contract, [handover](../PROJECT_HANDOVER_CONTEXT.md),
  [progress log](milestone-2-progress-log.md).

Full backend suite: 209 tests run, 200 passed, nine optional PostgreSQL tests skipped.
Eight focused tests passed, including rollback and latest-version filtering.
Final targeted alert regression run: 15 tests passed after serializer adjustments.
SQLite tests execute real ORM persistence and SQL predicates on isolated memory
data; they do not prove PostgreSQL lock scheduling. Application database URLs
were disabled for these runs. No local/demo records or image files were deleted.
Frontend TypeScript/Vite build passed. Final focused/lint results are recorded in
the progress log. `git diff --check` passed (Windows line-ending notices only).

The complete filtered set is aggregated in server memory before pagination,
consistent with existing reporting. Large deployments need SQL aggregation and
performance work. Query reads use normal transaction isolation, not a guaranteed
multi-statement snapshot during concurrent writers. PostgreSQL concurrent-request
testing remains outstanding; connected browser verification is complete as
recorded below. The existing
suite emitted nonfatal Ultralytics asset-network warnings and an Alembic
deprecation warning. Scoring/model/policy remain provisional as before.

### Phase 8.1D connected browser sign-off — 2026-11-13

Authenticated verification completed at `http://127.0.0.1:5173`; the browser's
`localhost:5173` origin did not share the session and redirected to login. All
observation risk facets were checked and remain individual-finding filters:
All 27, Pending 1, Critical 2, High 11, Moderate 16, Low 13. The displayed
explanation states that each card carries the observation's highest confirmed
risk. The mixed-risk High-45 observation appears in High, Moderate, and Low.
Reference `img-obs-1852c096` showed overall High 60, provisional, one Pending;
assessment #50 remained High 60 and #51 remained Pending. The expanded finding
breakdown, separate safety decision, both evidence previews, and assessment
controls were present. No-supported-finding cards retain the not-safe disclaimer.
Responsive checks at 390, 768 and 1280 pixels showed no horizontal overflow;
mobile navigation opened and Escape returned focus to its trigger.

Read-only GET snapshots of observations (including assessment/audit metadata)
and alerts matched before/after: 27 observations, 13 alerts, canonical digest
`20ee15da920d35ef6b848612ba8e0371c57deb1121658e55ba9c7f781a345c3f`. Alert
statuses remained 5 open, 1 acknowledged, 5 resolved and 2 dismissed. No live
observation with every finding Pending exists, so this state was not exercised
in the browser; isolated tests cover it. Connected Phase 8.1D verification is
complete and ready for Git sign-off. No saved data was changed.
