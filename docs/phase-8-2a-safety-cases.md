# Phase 8.2A Safety Case API — Read-Time Contract

This data model and grouping policy was documented before API implementation.
The implementation follows this contract and does not add a schema migration.

## Architecture decision

Represent a safety case as a read-time grouping of the existing persisted alerts
by their required `observation_id` foreign key. A case is not a new alert, does
not receive a lifecycle row, and does not replace any assessment or evidence
snapshot. Its stable identifier is `observation:<observation_id>`; there is at
most one case for an observation, and only observations with one or more alerts
have a safety case. This avoids a schema migration and leaves historical data
and existing alert APIs compatible.

Case reads load observations, alerts, hazards, assessments, and evidence metadata
with eager relationship loading. Group and filter cases before pagination so a
page never splits an observation's child alerts. The first implementation may
aggregate candidate rows in application memory, as existing reporting does;
case counts still represent unique cases and alert counts are reported
separately. A future SQL aggregate can replace this read implementation without
changing the response shape. Query boundaries use timezone-aware, half-open
observation time (`start` inclusive, `end` exclusive).

## Case grouping and lifecycle rules

- Group every persisted alert by its `observation_id`, including historical
  resolved and dismissed alerts. Do not deduplicate child alerts or infer a
  case from findings that have no alert.
- `unresolved_alert_count` counts children whose existing status is `open` or
  `acknowledged`.
- Derive `case_status` conservatively: `open` if any child is open; otherwise
  `acknowledged` if any child is acknowledged; otherwise `resolved` only when
  every child is resolved; `dismissed` only when every child is dismissed;
  otherwise `mixed_closed` (for example, resolved plus dismissed). Thus an Open
  plus Resolved case is Open and can never look fully resolved.
- `review_required` is true if any child alert requires review. Preserve each
  alert's correction marker, historical band, current assessment, and snapshot.
  Include assessment correction history from the existing observation metadata
  in case detail; do not construct or persist a second audit trail.
- Evidence availability is a boolean derived by resolving the existing safe
  image-storage metadata for `original` and `annotated` variants. Return no
  filesystem paths or image bytes in case list/detail JSON. Existing authenticated
  observation image routes remain the way the client loads previews.
- The observation's score/band/status comes from the Phase 8.1D authoritative
  summary; this API adds no risk calculation. Individual alert bands remain the
  historical alert snapshots.
- Case lifecycle is display-only. Existing `PATCH /alerts/{alert_id}/status`
  remains the only lifecycle mutation and keeps its Safety Officer/Admin
  authorization and forward-only per-alert transitions. There is no bulk case
  action in Phase 8.2A.

## Endpoint contract

`GET /safety-cases?work_area=...&status=...&start=...&end=...&search=...&sort=newest|oldest&limit=20&offset=0`

Authenticated; same reader authorization as alert history. `status` filters the
derived case status (`open`, `acknowledged`, `resolved`, `dismissed`, or
`mixed_closed`), not individual alerts. `search` matches observation ID or the
stable case ID. The response returns `total_cases` (unique matching
observations), `total_alerts` (individual alerts in those cases), `limit`,
`offset`, and paginated `items` sorted by observation timestamp with observation
ID as a deterministic tie-breaker. `work_area` is exact-match. Invalid or
timezone-naive dates are rejected consistently with existing observation query
behavior.

`GET /safety-cases/{observation_id}` returns one complete case or 404. The
response shape is:

```ts
type SafetyCaseStatus = 'open' | 'acknowledged' | 'resolved' | 'dismissed' | 'mixed_closed';
type SafetyCase = {
  case_id: `observation:${string}`;
  observation_id: string;
  observed_at: string;
  work_area: string | null;
  evidence: { original_available: boolean; annotated_available: boolean };
  overall_risk_score: number | null;
  overall_risk_band: 'Low' | 'Moderate' | 'High' | 'Critical' | null;
  overall_risk_status: string;
  overall_risk_provisional: boolean;
  case_status: SafetyCaseStatus;
  alert_count: number;
  alert_status_counts: Record<'open' | 'acknowledged' | 'resolved' | 'dismissed', number>;
  unresolved_alert_count: number;
  review_required: boolean;
  alerts: AlertDetailResponse[];
  findings: PersistedHazardResponse[];
  assessment_corrections: AssessmentCorrectionAudit[];
};

type SafetyCaseListResponse = {
  total_cases: number;
  total_alerts: number;
  limit: number;
  offset: number;
  items: SafetyCase[];
};
```

Supported case-status filters are exactly `open`, `acknowledged`, `resolved`,
`dismissed`, and `mixed_closed`. For an unfiltered list, `total_cases` counts
unique observation IDs after filtering and before pagination; `total_alerts`
counts all individual child alerts in that same filtered set, including alerts
outside the current page. Inside each item, `alert_count` counts all children,
`alert_status_counts` reports all four existing lifecycle states including zero
counts, and `unresolved_alert_count` counts only open and acknowledged children.

`alerts` preserves each existing alert ID, status, timestamps, original risk band,
decision snapshot and correction review fields. `findings` includes the complete
assessment version history. Existing `/alerts`, `/alerts/{id}` and alert status
endpoints remain unchanged.

## Phase 8.2B client handoff

Use `fetchSafetyCases(filters)` for the paginated list and display
`total_cases` separately from `total_alerts`. Group expansion should use
`fetchSafetyCase(observation_id)` to retrieve complete findings, all individual
alerts, correction history, and child status counts. Render `case_status` as a
derived summary while preserving the child alert statuses and IDs in the
details. Lifecycle buttons must continue to call `updateAlertStatus(alert_id,
status)` for one named child at a time; there is no case-level mutation API.
Use the observation image URL helper with the case observation ID and
`original`/`annotated` variants only when the corresponding evidence flag is
true. Keep historical alert `risk_band` distinct from the case's current
overall observation risk summary.

## Compatibility and migration

No schema migration is planned. New authenticated GET endpoints are additive.
The Alert Register's existing `GET /alerts` and lifecycle client remain
unchanged until Phase 8.2B opts into the case API. No saved alert, assessment,
observation, evidence file, lifecycle status, scoring result, or model weight is
rewritten by case reads. Pagination is over cases, never alert rows.

## Verification plan

Use isolated SQLite/in-memory fixtures for one/multiple alerts per case, mixed
states, review-required corrected assessments, no duplicate grouping, status
filters, time/work-area/search filters, deterministic pagination, auth, and
legacy alert API compatibility. No tests write to `safesite_local` or
`safesite_demo`.
