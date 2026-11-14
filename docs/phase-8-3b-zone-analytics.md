# Phase 8.3B — Evidence-Linked Zone Analytics

## Scope and preserved behavior

Phase 8.3B extends the authenticated `GET /analytics/zones` contract and replaces
the summary-only Zone Analytics page with a read-only investigation workspace.
The existing `total_violations`, `violation_count`, rankings, finding lineage,
`risk_level_distribution`, and legacy alert fields retain their prior meanings.
The highest/lowest rankings remain supported detected-hazard-row frequency,
with deterministic lexical tie-breaking; the UI labels them “Most/Fewest
recorded hazard findings.” No scoring policy, alert policy, recurrence
calculation, persistence schema, or saved record changes were made.

## Zone summary API

`GET /analytics/zones?start=<offset-datetime>&end=<offset-datetime>` is
authenticated. Omitting either date leaves that side unbounded; omitting both
preserves the prior all-history query. Date bounds apply to
`Observation.observed_at` as a timezone-aware half-open interval
`start <= observed_at < end`; values are normalized to UTC and naive or
inverted ranges return HTTP 422.

Legacy response fields remain present. Additive response fields are:

```ts
type ZoneSummaryAdditions = {
  scope: { start: string | null; end: string | null; interval: '[start,end)' };
  metric_units: Record<string, string>;
  unique_observation_count: number;
  valid_latest_completed_assessment_count: number;
  pending_latest_assessment_count: number;
  incomplete_latest_assessment_count: number;
  overall_observation_risk_distribution: Record<
    'Low' | 'Moderate' | 'High' | 'Critical' | 'pending' | 'incomplete' | 'no_supported_findings', number
  >;
  provisional_observation_count: number;
  individual_alert_count: number;
  alert_status_counts: Record<'open' | 'acknowledged' | 'resolved' | 'dismissed', number>;
  all_unresolved_alert_count: number;
  safety_case_count: number;
};
```

Each `violations_by_work_area[]`/`most_common_violation_by_area[]` item now also
contains `violation_metrics[]`, `observation_count`, valid/pending/incomplete
latest-finding assessment counts, a distinct-observation overall risk
distribution, provisional observation count, alert counts/statuses, unresolved
individual-alert count, and safety-case count. `violation_metrics[]` gives the
supported hazard category counts and contributing persisted IDs for category
selection.

Metric units and important distinctions:

- `total_violations`, area `violation_count`, and `violation_metrics[].count`
  count supported detected-hazard rows. Multiple rows in one observation count
  separately.
- `unique_observation_count` and each area's `observation_count` count distinct
  observation IDs that contain at least one supported finding. Observations
  with no supported findings do not enter this analytics population.
- Valid/pending/incomplete latest assessment counts count one effective
  assessment state per supported detected-hazard ID, not assessment history
  versions. A malformed latest completed score is incomplete and not scored.
- `risk_level_distribution` is the preserved legacy per-finding distribution
  using the latest stored completed band (unknown/missing/pending bands fall
  into `pending`). It remains distinct from the new observation-level summary.
- `overall_observation_risk_distribution` counts distinct observations using
  Phase 8.1D's `overall_risk_summary`: max valid latest score, existing
  authoritative band policy, no sum/average. Provisional is counted separately
  and can coexist with a band. Pending, incomplete, and no-supported-finding
  states do not invent scores.
- New alert totals/statuses count unique alert IDs on observations with at least
  one supported finding; Open and Acknowledged are both unresolved. Legacy
  `open_alert_count`, `unresolved_alert_count`, and `resolved_alert_count`
  remain linked-supported-finding counts for compatibility and retain their
  prior overlap semantics.
- `safety_case_count` counts distinct observations in this population with one
  or more persisted alerts. A case is not an extra alert or hazard.
- `work_area` remains trimmed free text. Null/blank and the existing placeholder
  values are grouped as Zone Analytics' `Unspecified` bucket; case and internal
  spelling remain distinct for named areas.

## Shared supporting-observation API

```http
GET /analytics/finding-observations
  ?work_area=Zone%20A
  &hazard_type=missing_safety_helmet
  &start=2026-03-01T00:00:00-05:00
  &end=2026-04-01T00:00:00-04:00
  &area_mode=zone
  &sort=newest
  &limit=10
  &offset=0
```

The endpoint requires authentication. `work_area`, hazard category, date bounds,
area mode, sort, limit and offset are optional. Supported `hazard_type` values
are canonical persisted PPE categories; unsupported values return 422.
`area_mode=zone` preserves the Zone `Unspecified` bucket. `area_mode=recurrence`
excludes the documented unknown placeholders and uses the existing conservative
trim-only named-area identity, ready for Phase 8.3C reuse. Date bounds use the
same timezone-aware `[start,end)` observation timestamp convention. Sort is
newest/oldest with observation ID as deterministic tie-breaker; page size is
1–100.

```ts
type FindingObservationList = {
  total_observations: number;       // unique matching persisted observation IDs
  total_matching_findings: number;  // matching supported detected-hazard rows
  limit: number;
  offset: number;
  items: Array<ObservationDetailResponse & {
    matching_detected_hazard_ids: number[];
    evidence: { original_available: boolean; annotated_available: boolean };
    safety_case_id: string | null;  // observation:<id> when an alert case exists
  }>;
};
```

Matching requires both an allowed supported source label and its corresponding
canonical persisted hazard category. Counts and page IDs are queried before
hydrating one selected observation page; bounded select-in loads return all
hazards/assessments, observation alerts, Phase 8.1D risk summary, and evidence
lineage without one request per observation or ORM N+1 access. The endpoint
does not write data. Image bytes continue to use authenticated
`/observations/{observation_id}/image/{original|annotated}` access.

## Frontend behavior

The Zone page applies the same local-time date inputs to aggregate and detail
requests; selected end date is converted to the next local midnight, then
serialized as an offset-bearing UTC instant. Invalid local ranges are blocked.
Area comparison presents hazard-row frequency, distinct observations,
assessment completeness, risk distribution by distinct observation, and alert
and case counts with the unit beside each measure. A work-area investigation
opens a paginated observation drawer; selecting a supported hazard category
narrows the supporting finding IDs without duplicating observation rows. Each
observation presents overall risk/provisional state, matching finding/latest
assessment, thumbnail, optional original/annotated viewer, Safety Incidents
deep link, and a conditional case link.

The case link uses `#alerts?observation_id=<id>`. `AlertsPage` resolves that
existing case ID through `GET /safety-cases/{observation_id}` and opens the
existing accessible case drawer; ordinary `#alerts` navigation remains
unchanged. The supporting-observation drawer reuses the existing modal focus
trap and image viewer.

## Validation and limitations

Focused zone/recurrence tests cover distinct observation units, multiple
findings/alerts, latest assessment correction, malformed latest values,
date-bound validation, category filtering contract, empty page shape and
authentication. Full backend, frontend build, lint and diff checks are recorded
in the Phase 8.3B progress entry.

Aggregate analytics still loads the filtered supported findings and groups
them in application memory, as before; it is eager-loaded to avoid N+1 reads
but does not yet use database group-by aggregation. The drill-down list is
paginated in SQL. Alerts in the new all-alert metrics are scoped to observations
with at least one supported finding. Work-area corrections reclassify those
historical observations under the current free-text value, consistent with
existing analytics semantics. Connected verification is only claimed when the
browser has an authenticated session; no live writes are used in verification.

## Final connected verification attempt

On 2026-11-14 the shared integrated browser was checked at the required origin,
`http://127.0.0.1:5173/#login`. It displayed the sign-in page, so authenticated
UI checks and before/after observation/alert snapshots were not performed.
Per the verification instruction, no sign-in retry or server restart was made.

The browser's same-origin Vite proxy was probed without credentials. Both
requests returned JSON (not Vite `index.html`): `/analytics/zones` returned
HTTP 401 `Authentication required`, while `/analytics/finding-observations`
returned HTTP 404 `Not Found`. This confirms that the `/analytics` proxy
forwards to a FastAPI server, and that the live app is not serving the new
supporting-observation route. The currently visible backend OpenAPI document
lists `/analytics/zones` but not `/analytics/finding-observations`; its zone
operation also lacks the new `start`/`end` parameters present in checked-out
source. This is a verified source/runtime mismatch, not an HTML/proxy fallback.
The proxy is configured for `/analytics` to `http://localhost:8000`; it should
be aligned to the established `127.0.0.1:8000` origin when the runtime is
refreshed, then both routes and the zone date parameters should be confirmed in
OpenAPI before connected sign-off.

Consequently, live metric totals, date semantics, filters, drill-down,
evidence, deep links, responsive/accessibility behavior, and persisted-data
before/after equality remain unverified in this attempt. No observation,
assessment, alert, image, or account data was changed. Phase 8.3B automated
validation remains as recorded above, but connected sign-off is outstanding.

## Controlled backend reload and connected sign-off status — 2026-11-14

The prior listener was confirmed as the SafeSite workspace backend (PID 33824,
project working directory and .venv-yolo command); only that process was
stopped. The approved start_local_backend.ps1 was run once. It derives a
local PostgreSQL URL pinned to safesite_local and launches Uvicorn without
migrations, resets, seeding, or account bootstrap. No database records or
evidence were changed by the reload.

After startup, /health returned 200. Live OpenAPI contains both
/analytics/zones with start and end, and /analytics/finding-observations
with work-area, hazard, date, sorting, and pagination parameters. Both routes
return 401 JSON when unauthenticated. Same-origin requests from the Vite
frontend to both routes also returned 401 JSON, confirming proxy forwarding and
no HTML fallback.

Authenticated browser verification could not proceed. The only shared
SafeSite page, ID 4d12a393-54c1-4ff8-8fed-75d26552ccf3, is still at
http://127.0.0.1:5173/#login; no authenticated Safety Officer dashboard or
separate authenticated page is shared. The user may be signed in from a
different tab/window or browser context, but that cannot be identified from
the shared session. No authenticated initial/final observation or alert
snapshots were captured. Metrics, filters, drill-down, evidence, deep links,
keyboard interactions, responsive layouts, and data-preservation comparison
remain unverified. Phase 8.3B connected sign-off is therefore blocked on the
authenticated browser session; automated implementation checks remain as
previously recorded.

## Shared browser retry status — 2026-11-14

The controlled integrated-browser page was checked again without interacting
with the login form. Shared page ID 4d12a393-54c1-4ff8-8fed-75d26552ccf3
remains at http://127.0.0.1:5173/#login and displays Login failed; the browser
reported HTTP 502 responses. Authentication is unavailable in this shared
session. No login was resubmitted, no service was restarted, and no credential
or token was copied into verification notes. No authenticated observation or
alert snapshots were possible, so persisted-data equality is not verified.
Connected sign-off remains outstanding.

For manual verification in Chrome, open http://127.0.0.1:5173, sign in as an
authorized Safety Officer, and open Zone Analytics. Compare dashboard totals
with GET /analytics/zones?start=<UTC-inclusive>&end=<UTC-exclusive>; select an
area/category and compare the drawer's unique-observation total and page items
with GET /analytics/finding-observations. Check Clear Filters, area/category
selection, pagination without duplicate observation IDs, image previews,
assessment lineage, #incidents observation links and #alerts case links. Test
Escape and focus restoration for drawers/previews and inspect 390px, 768px,
and 1280px widths for overflow. Before and after browsing, compare read-only
observation IDs and assessment histories plus alert IDs, statuses, and
lifecycle timestamps. Do not submit edits or status actions.

#### Phase 8.3B final connected sign-off attempt - 2026-11-14

The integrated-browser page handle supplied for `http://127.0.0.1:5173` (`4d12a393-54c1-4ff8-8fed-75d26552ccf3`) was unavailable to the browser tool (`Page ... not found`). Opening the same origin in a new integrated-browser page also failed. Therefore the current page URL, authentication state, and login-request result could not be inspected; this attempt does not establish that login failed or that the authenticated browser is in a different context. No login was submitted, no service was restarted, and no credentials or tokens were accessed. Authenticated API snapshots and Zone Analytics UI checks could not be performed, so connected sign-off remains outstanding.

Manual read-only checklist: share the active authenticated tab at `http://127.0.0.1:5173` in the integrated browser (same host and port). Compare Zone Analytics totals with `GET /analytics/zones?start=<inclusive>&end=<exclusive>` and supporting-observation items/totals with `GET /analytics/finding-observations`. Check distinct-observation paging, date filters/Clear Filters, finding versus overall risk, Pending/provisional state, evidence previews, `#incidents` and `#alerts?observation_id=...` navigation, keyboard Escape/focus restoration, and 390px/768px/1280px layouts. Capture read-only observation/assessment-history and alert-status/timestamp snapshots before and after; do not submit assessment or alert actions.
