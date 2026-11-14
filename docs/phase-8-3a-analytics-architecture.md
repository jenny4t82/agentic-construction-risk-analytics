# Phase 8.3A — Zone and Recurrence Analytics Architecture Audit

Date: 2026-11-14
Branch: `revamp/milestone-2`
Checkpoint: `4833343a8228b55628fd4ad6ee7ee7adea1da99d`

## Scope and outcome

This is an architecture audit and implementation plan. It makes no application
code, API, schema, database, model, or UI changes. The current branch was
`revamp/milestone-2` at the Phase 8.2 checkpoint and its working tree was clean
before documentation updates. No live database writes or Git history actions
were performed. The integrated browser was at the login page, so this phase
does not claim a connected live-data review.

Primary implementation sources are [`backend/app/analytics.py`](../backend/app/analytics.py),
analytics response models/routes in [`backend/app/main.py`](../backend/app/main.py),
[`frontend/src/components/ZoneAnalyticsPage.tsx`](../frontend/src/components/ZoneAnalyticsPage.tsx),
[`frontend/src/components/RecurrenceAnalyticsPage.tsx`](../frontend/src/components/RecurrenceAnalyticsPage.tsx),
and tests [`backend/tests/test_zone_analytics.py`](../backend/tests/test_zone_analytics.py)
and [`backend/tests/test_recurrence_analytics.py`](../backend/tests/test_recurrence_analytics.py).

## Existing data and request architecture

`Observation` owns `observed_at`, nullable free-text `work_area`, image
metadata, and a one-to-many relationship to `DetectedHazardRecord`.
Each detected hazard has versioned `RiskAssessment` rows and may have multiple
related `Alert` rows. An alert stores its own risk-band snapshot, status and
lifecycle timestamps; it does not represent a safety case. Phase 8.2 derives
a case by grouping alerts on `observation_id`, with stable ID
`observation:<observation_id>`.

The existing authenticated endpoints are:

| Endpoint | Existing behavior |
| --- | --- |
| `GET /analytics/zones` | Full-history supported PPE hazard and alert snapshot. No date, area, sort, or pagination parameters. |
| `GET /analytics/work-area-recurrence?start=&end=` | Optional observation-time window, all matching groups and contributing observation IDs; no pagination. |
| `GET /observation-query` | Observation filters for risk, exact work area, half-open dates, observation ID, sort and pagination; backend computes global filtered totals/facets before paging. It has no hazard-category filter. |
| `GET /observations/{observation_id}` | One observation with detected hazards, all assessment versions and Phase 8.1D observation-level risk summary. |
| `GET /observations/{observation_id}/image/{original\|annotated}` | Authenticated evidence file retrieval. |
| `GET /assessments/{assessment_id}` | One assessment's context, current calculation, audit history and reconciliation details. |
| `GET /safety-cases` and `GET /safety-cases/{observation_id}` | Phase 8.2 case list/detail. Cases exist only where one or more alerts exist; detail has the observation's findings, assessment history and evidence-availability flags. |

The browser client already has `fetchZoneAnalytics`,
`fetchWorkAreaRecurrence`, `queryObservations`, `fetchObservationDetail`,
`fetchAssessmentContext`, and `fetchSafetyCase`. Reusable frontend pieces are
`ObservationThumbnail`, `ObservationEvidenceViewer`, `ObservationRow`,
`incidentLink`/`incidentTarget`, `formatHazardType`, and the safety-case
detail drawer. `incidentLink` supports observation ID, optional assessment ID,
and existing observation filters. Zone Analytics currently has no onward
links. Recurrence renders observation IDs as text and its button only opens
ordinary Observation History; neither analytics page currently opens a
specific observation, assessment, image, or safety case.

## Metric definitions and semantics

### Zone Analytics

The zone endpoint first loads all supported detected-hazard records with
`selectinload` for the observation, assessment versions and related alerts.
It keeps rows where the source label is supported and maps to the persisted
hazard type. There is no observation-time filter. The endpoint is a full-history
snapshot, calculated in application memory.

| Current field or display | Exact unit and meaning |
| --- | --- |
| `total_violations`; `AreaMetric.violation_count`; `ViolationMetric.count` | Supported detected-hazard rows, not unique observations, workers, cases or assessment versions. Multiple detections in one observation count as multiple violation rows. |
| `observation_ids` | Unique IDs associated with the selected finding rows. This is lineage, not a top-level unique-observation total. |
| `detected_hazard_ids` | IDs of the contributing persisted hazard rows. |
| `risk_level_distribution` | One bucket per supported hazard row, using the latest assessment version for that hazard. A completed row with a nonempty known band contributes that band; missing, pending or unknown-band values contribute `pending`. It does not validate the numeric score against the band and is not Phase 8.1D's observation-level maximum. |
| `open_alert_count` | Related individual alert rows with `status=open`, attached to supported hazards. |
| `unresolved_alert_count` | Related individual alert rows with `status=open` or `acknowledged`, attached to supported hazards. Open is included in this number; the fields are overlapping, not additive buckets. |
| `resolved_alert_count` | Related individual alert rows with `status=resolved`, attached to supported hazards. Dismissed alerts are not exposed by a separate field. These are not all global alerts if an alert is not linked through one of the included hazard records. |
| highest/lowest area; most-common finding | Ranked by supported hazard-row frequency with deterministic lexical tie-breaking, not by risk severity, unique observations, or alert count. |

The endpoint does **not** provide separate counts for unique observations,
latest completed assessment results, all assessment-version rows, all
individual alerts, safety cases, acknowledged alerts, dismissed alerts, or
pending versus malformed/incomplete latest assessment states. Those must not
be inferred from `total_violations` or summed from the displayed risk/alert
fields. The current frontend exposes supported violation frequency, highest
and lowest frequency area, open/unresolved/resolved alert counts, per-area
violation rows, most-common supported hazard and the latest-finding risk
distribution. It has no filters or evidence-linked drill-down.

For comparison, Phase 8.1D's `overall_risk_summary` uses the latest version per
finding, accepts only a valid numeric score, classifies via the existing risk
policy, then chooses the maximum confirmed score per observation. It exposes
completed, pending, incomplete and total finding counts and provisional state.
Zone's current distribution is a per-finding legacy summary, not that
observation-level result. A new display must label these separate units and
must not calculate a second overall risk.

### Recurrence Analytics

`GET /analytics/work-area-recurrence` includes a hazard only when its
`source_label` is supported, the label maps to its persisted `hazard_type`,
and the foreign-key observation ID matches the loaded observation. It groups
by `(normalized named work area, canonical hazard_type)` and stores distinct
`observation_id` values in a set. A pair is repeated at two or more distinct
observation IDs. Multiple detection rows in one observation and additional
assessment versions therefore do not increase the pair's count. Different
hazard categories and different areas remain separate groups.

Work-area normalization is deliberately narrow: trim leading/trailing
whitespace, preserve case and internal whitespace/spelling, and exclude null,
blank, and case-insensitive `unspecified`, `unknown`, or
`unassigned work area`. Thus `Zone A`, `zone a`, `Zone-A`, and `Zone  A` remain
distinct labels. Other ad hoc placeholders are not recognized as unknown.
Zone Analytics uses the same trimmed label for named areas but buckets values
excluded from recurrence into `Unspecified`. These are different and explicit
unknown-area semantics; do not silently merge them.

The optional bounds are timezone-aware, converted to UTC, and applied to
`Observation.observed_at` with a half-open interval (`start <= observed_at <
end`). Missing bounds mean all history. Filtering is by observation time,
not detection or assessment time. Missing/pending/incomplete assessment data
does not exclude an otherwise supported hazard observation because recurrence
does not load or use assessments. The observation's operator-supplied
`repeated_count` is not a recurrence input. Recurrence describes repeated
recorded categories and areas only; it cannot identify workers, prove a
person-level repetition, describe accidents, or measure risk severity.

The recurrence query uses one supported-hazard query plus eager-loaded
observations rather than N+1 lookups, then aggregates all rows and returns all
observation IDs in memory. It has no server pagination. Zone Analytics similarly
eager-loads related collections and computes the full snapshot in memory.
These avoid N+1 access but remain unbounded in result size.

## Confirmed limitations and backward-compatible recommendations

1. Zone metrics overload the word “violations.” Keep the existing fields for
   compatibility, but add explicit unit metadata and named counts for unique
   observations, supported hazard rows, latest valid completed finding
   assessments, incomplete/pending findings, individual alerts by lifecycle,
   and safety cases. Counts should be independently derived from their own
   rows/IDs; document overlaps. A safety case count is unique observations with
   one or more alerts, not an additional hazard or alert count.
2. Add observation-time `start`/`end` to Zone's aggregate endpoint so chart
   statistics and recurrence use the same half-open window. Preserve the
   unfiltered response when bounds are omitted. Date parameters must require
   offsets and reject inverted ranges consistently.
3. Zone risk buckets trust a persisted completed band's value; they do not
   confirm a valid score or recalculate the band. Phase 8.3B should use the
   existing authoritative per-finding validation/classification helper (shared
   with Phase 8.1D where practical) and label the distribution as latest
   finding assessments. Do not sum, average, or change scoring thresholds.
4. Current Zone and Recurrence APIs return full, unpaginated result sets. Use
   explicit deterministic ordering and page the supporting-observation
   drill-down by unique observations. If aggregate payloads become large,
   move grouping to database aggregation without changing metric definitions.
5. Recurrence sends every matching observation ID in the group response. This
   is useful lineage at current scale but can grow substantially. Phase 8.3C
   should paginate the supporting-observation endpoint and may later omit
   unbounded ID arrays only through an additive/versioned contract change.
6. Work area is mutable free text, not a zone entity. Correcting an
   observation's work area re-buckets that historical observation in current
   analytics (the stored correction history is audit, not an as-of analytics
   dimension). Keep this limitation visible and agree on aliases/unknown
   normalization before broader canonicalization.
7. The existing query-by-observation API cannot filter observations by a
   specific supported hazard category, and recurrence's ID list alone does
   not supply paginated observation detail, evidence flags, or case
   availability. A focused authenticated drill-down contract is required;
   do not have the browser infer global counts from a loaded page or issue
   one request per observation just to assemble group membership.

## Recommended Phase 8.3 API additions

### Zone summary (additive extension)

Extend `GET /analytics/zones` with optional `start` and `end` observation-time
bounds. Keep every current response property and full-history behavior when
no bounds are provided. Add explicit `metric_units`/semantics metadata and
counts at top level and per area. Proposed fields (names can be finalized in
8.3B):

```ts
type ZoneAnalyticsV2Fields = {
  scope: { start: string | null; end: string | null; interval: '[start,end)' };
  metric_units: {
    observations: 'distinct observation_id';
    detected_hazards: 'supported detected_hazard_id';
    latest_assessments: 'one effective assessment per detected_hazard_id';
    alerts: 'individual alert_id';
    safety_cases: 'distinct observation_id with one or more alerts';
  };
  totals: {
    unique_observation_count: number;
    supported_hazard_count: number;
    latest_completed_finding_count: number;
    latest_pending_finding_count: number;
    latest_incomplete_finding_count: number;
    individual_alert_count: number;
    alert_status_counts: Record<'open' | 'acknowledged' | 'resolved' | 'dismissed', number>;
    unresolved_alert_count: number;
    safety_case_count: number;
  };
  areas: Array<{
    work_area: string;
    observation_count: number;
    detected_hazard_count: number;
    latest_finding_risk_distribution: Record<'Low' | 'Moderate' | 'High' | 'Critical' | 'pending' | 'incomplete', number>;
    individual_alert_count: number;
    alert_status_counts: Record<'open' | 'acknowledged' | 'resolved' | 'dismissed', number>;
    unresolved_alert_count: number;
    safety_case_count: number;
  }>;
};
```

Keep legacy field definitions, do not silently redefine `total_violations`,
and label frequency rankings as hazard-row counts. `latest_completed_finding`
counts one valid current assessment result per finding, not all historical
assessment versions. `safety_case_count` must be a distinct-observation count
over alert presence; the alert status counts remain child-alert counts.

### Shared paginated supporting-observation endpoint

Add one authenticated endpoint reusable by both analytics pages:

```http
GET /analytics/finding-observations?work_area=Zone%20A&hazard_type=missing_safety_helmet&start=...&end=...&area_mode=recurrence&sort=newest&limit=20&offset=0
```

Proposed response:

```ts
type FindingObservationList = {
  total_observations: number;       // distinct matching observation IDs
  total_matching_findings: number;  // persisted supported hazard rows
  limit: number;
  offset: number;
  items: Array<ObservationDetailResponse & {
    matching_detected_hazard_ids: number[];
    evidence: { original_available: boolean; annotated_available: boolean };
    safety_case_id: string | null;  // observation:<id> only when alert case exists
  }>;
};
```

`area_mode=recurrence` applies exactly the existing named-area trim, case and
placeholder rules. Zone mode must support the existing `Unspecified` bucket
without treating it as a validated area. `hazard_type` uses the canonical
persisted PPE category, and matching detection rows must still pass the
existing source-label/category consistency test. Filter and page unique
observations after matching; preserve all matching hazard IDs within each
item. Return the existing `ObservationDetailResponse` fields so the UI can use
Phase 8.1D's authoritative overall summary and full assessment history rather
than reconstructing them. Evidence flags can reuse the safe image-availability
helper already used by safety cases. Case IDs are nullable references, not
new records. Return filtered totals before pagination. This avoids N+1 browser
requests and keeps case/evidence ownership in existing endpoints.

The frontend can use `GET /observations/{observation_id}/image/{variant}` for
original/annotated previews, `incidentLink(observation_id, assessment_id,
filters)` for direct Safety Incidents navigation, and the existing
`GET /safety-cases/{observation_id}` when `safety_case_id` is present. Add an
additive Alert Register deep-link query such as `#alerts?observation_id=...`
only if the UI must open the case drawer directly; existing plain `#alerts`
links must remain intact.

## Recommended UI architecture

### Phase 8.3B — Zone Analytics

- Add an observation-time range control above the summary; apply identical
  bounds to all statistics and drill-downs. Keep a clear all-history state.
- Present separate cards for unique observations, supported hazard rows,
  latest completed finding results, individual alerts/unresolved alerts, and
  safety cases. Label count units and avoid summing overlapping status counts.
- Retain the finding-risk distribution as per-finding latest assessment data.
  Keep risk severity visually and textually separate from violation frequency.
- Compare work areas by supported hazard-row frequency, with unique-observation
  counts alongside; do not label the most frequent area “highest risk.”
- Make hazard/area rows clickable. Open a paginated observation drawer/panel
  using the shared drill-down endpoint. Each item shows image thumbnail, date,
  work area, overall observation risk/provisional state, matching finding and
  latest assessment; expand to all assessments and use existing evidence
  viewer on demand.
- Link to Safety Incidents with the matching assessment ID and preserved
  context. Offer a safety-case link only when the returned case reference is
  non-null. Do not duplicate assessment or case detail implementations.

Reuse authenticated API helpers, `ObservationThumbnail`,
`ObservationEvidenceViewer`, `incidentLink`, and shared date/formatting
components. New frontend components should be focused on the analytics
summary/chart and an accessible observation drill-down drawer. No new design
system or scoring service is needed.

### Phase 8.3C — Recurrence Analytics

- Keep the existing “same supported PPE category, same named area, at least
  two distinct observation IDs” definition and current category/area matching.
- Render the backend `groups` as an area-by-hazard matrix. Cells show exact
  distinct observation counts; style `is_repeated` separately from count and
  never use a risk color scale. Preserve deterministic area/hazard ordering.
- Keep the current observation-time window filter and explain the half-open
  boundary/local-time conversion. Make the selected window visible in the
  matrix and all supporting rows.
- Make a matrix cell open the shared paginated drill-down with its area,
  canonical hazard type, and date bounds. Compare the list's unique-observation
  total to the matrix cell's `observation_count`.
- Show supporting observation cards with thumbnails, date, overall risk
  summary/provisional marker, matching findings/assessment links, and
  conditional safety-case navigation. Use evidence previews only when opened.
- Keep clear explanatory text: recurrence is recorded PPE finding frequency
  across distinct observations; it neither identifies workers nor measures
  overall risk, accident frequency, compliance, or causal factors. State that
  assessments may be missing and a finding can still count as recurrence.
- Keep named-area and unknown-area behavior explicit; do not silently merge
  case or whitespace variants.

Reuse the same observation drawer, cards, image components, and case/incident
links introduced in 8.3B. A backend matrix endpoint is not required at current
scale because the recurrence summary already returns area/category groups;
the paginated supporting-observation API is required.

## Implementation breakdown and verification

### Phase 8.3B — Zone Analytics implementation

Dependencies: this audit's metric vocabulary and the shared drill-down contract.
Additive backend work: timezone-aware half-open date filters, explicit metric
units and independent counts, valid latest-finding risk classification using
existing scoring policy, and paginated unique-observation drill-down. Frontend
work: date filter, unit-labeled cards, frequency comparison, clickable
breakdowns, responsive keyboard-accessible drill-down, image and existing
navigation integration.

Focused backend tests: exact row/observation/assessment/alert/case denominators;
multiple findings in one observation; alerts across every lifecycle; latest
assessment correction and malformed values; date endpoints; work area and
unknown buckets; unique-observation paging, stable sorting, authorization, and
filter totals. Frontend tests should cover chart-to-filter parameter mapping,
empty/error/loading states, drawer focus/Escape, and links. Run build, lint,
available frontend tests and `git diff --check`.

### Phase 8.3C — Recurrence Analytics implementation

Dependencies: 8.3B's shared drill-down and reusable observation/evidence
components. Preserve the current recurrence service and rules; add the shared
paginated evidence-rich observation contract with recurrence area normalization
and date bounds. Render the matrix and detail list without changing recurrence
calculation or risk/alert policy.

Focused tests: two detections in one observation remain one; another
observation makes a pair repeated; reassessment versions do not alter counts;
categories and areas remain separate; exact normalization and excluded
placeholders; missing assessments remain included; unknown areas remain
excluded; half-open boundaries/timezone conversions; group and drill-down count
consistency; stable pagination; no writes to repeated_count, scores, alerts or
assessment history. Verify matrix accessibility, responsive scroll behavior,
evidence loading, direct links and empty/error/loading behavior.

### Phase 8.3D — Connected verification and Git checkpoint

Use authenticated browser and read-only API snapshots against `safesite_local`.
Compare observation IDs/counts, hazard IDs, assessment histories, alert IDs,
statuses/timestamps, and image references before/after. Exercise area/date
filters, every chart/matrix drill-down, pagination, incident and case links,
image previews, focus/Escape and mobile/tablet/desktop layouts. Do not submit
assessment, work-area, or alert lifecycle mutations. Mark unavailable data
examples unverified rather than fabricating records. Run the full isolated
backend suite, frontend build/typecheck/lint/tests and diff check. Review
explicitly staged source/tests/docs for secrets or data files before a separate
checkpoint authorization.

Risks to track: free-text work-area identity, current-area reclassification of
old observations after an edit, unbounded aggregate result memory, unknown
assessment differences between legacy per-finding bands and authoritative
observation summaries, images missing from historical observations, and safety
cases existing only for observations with alerts. No Phase 8.3B implementation
was started here.

## Phase 8.3B implementation addendum — 2026-11-14

The Phase 8.3A proposals are now implemented for Zone Analytics. The additive zone response fields and exact denominators, authenticated date-aware endpoint, shared unique-observation pagination contract, unknown-area modes, preserved legacy semantics, frontend navigation behavior, and current limitations are specified in [`phase-8-3b-zone-analytics.md`](phase-8-3b-zone-analytics.md). The recurrence calculation and page remain unchanged; Phase 8.3C can consume the new endpoint with `area_mode=recurrence`.

At implementation time the integrated browser was signed out. No populated connected presentation checks or live data snapshots are claimed. Isolated tests, build, lint and diff validation are recorded in the Phase 8.3B progress section.
