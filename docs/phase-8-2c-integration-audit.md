# Phase 8.2C — Safety Case Integration Audit

Date: 2026-11-13
Branch: `revamp/milestone-2`
Connected origin: `http://127.0.0.1:5173`

## Repository audit

At the start of the audit, `frontend/src/components/AlertsPage.tsx` existed but
was still the prior individual-alert register: it called `fetchAlerts()` and
rendered each alert separately. The route was wired from `App.tsx`, but the new
case endpoints were not consumed. These described files did not exist:
`SafetyCaseSummary.tsx`, `SafetyCaseFilterBar.tsx`, `SafetyCaseCard.tsx`,
`SafetyCaseDetailDrawer.tsx`, `AlertRow.tsx`, and a safety-case data hook. No
dedicated safety-case stylesheet or `SafetyCaseSummary.md` artifact existed.

The backend case API, TypeScript contracts, and API client from Phase 8.2A were
present. Contract inspection confirmed that list totals are supplied by the
backend, case pagination occurs after grouping, case detail takes an
`observation_id`, and supported lifecycle filters include `mixed_closed`.

## Integration work

The Alert Register route now renders the case workspace. It consumes
`GET /safety-cases` with exact backend query names (`work_area`, `status`,
`start`, `end`, `search`, `sort`, `limit`, `offset`) and displays backend
`total_cases` and `total_alerts`, never deriving global totals from the current
page. It requests `GET /safety-cases/{observation_id}` when a case is opened.
The case card separates overall observation risk from derived case lifecycle,
shows individual-alert and unresolved counts, and flags review-required cases.
The responsive drawer contains authenticated original/annotated evidence,
finding assessment versions, correction history, individual alert rows, and
Safety Incidents links using the existing `#incidents?observation_id=...&assessment_id=...`
contract. Existing `#alerts` routing remains in place.

Each lifecycle button calls `updateAlertStatus(alert.alert_id, status)` for one
child alert. No case-level bulk action was added. Following a successful
transition the page refetches the case list and that observation's detail so
derived status and counts come from the backend. Existing role checks and API
authorization are retained. The drawer uses the application's modal focus
helper; nested dialogs are treated as topmost so image previews can retain
keyboard focus.

The Vite proxy was missing `/safety-cases`, causing Vite HTML to be parsed as
JSON. It now proxies that prefix to `http://127.0.0.1:8000`. Safety-case client
helpers now reject non-JSON and malformed JSON with an actionable `ApiError`.

## Connected verification and data preservation

The signed-in Safety Officer session at `127.0.0.1:5173` remained authenticated.
Read-only before/after API snapshots were identical:

- 27 observations, IDs preserved in both snapshots.
- 13 alerts, IDs 3–15, with status counts Open 5, Acknowledged 1, Resolved 5,
  Dismissed 2.
- No write requests were issued by verification.

The connected frontend correctly routed `/safety-cases` through Vite after the
proxy fix, but the running backend returned HTTP 404. Its live `/openapi.json`
also omitted both safety-case paths, while `/alerts` and `/observations` returned
200. The checked-out backend source does include the Phase 8.2A routes; therefore
the running backend process is serving an API version that does not include the
workspace's current source. The service was not restarted. Connected case
grouping, evidence/detail drawer, lifecycle refresh, and populated-card keyboard
checks remain unverified until the backend is launched/reloaded from this
workspace. The error state itself was clear (Not Found rather than a JSON parse
exception). At 390, 768, and 1280 CSS-pixel viewport widths, the rendered
register/error layout had no horizontal overflow. The authenticated before/after
snapshot pair matched; a later read-only request returned 401 after the browser
session expired. No credentials were exposed and no repeated sign-in attempt was
made.

No observation, alert, user, image, database, model-weight, or baseline changes
were made. The baseline branch/tag remain untouched. No Git staging or commit
was performed.

## Regression checks

- Full isolated backend suite: 219 passed, 9 PostgreSQL integration tests
  skipped because the test database was not configured. This includes safety
  case grouping/filtering/auth, alert forward transitions and dismissal,
  invalid transitions, role authorization, assessment correction/review
  lineage, and existing analytics tests.
- Frontend TypeScript/Vite build: passed.
- Frontend lint: passed with six existing warnings in OverviewPage,
  ZoneAnalyticsPage, AuthContext, App, and ObservationHistory; no new warning
  remains in the safety-case integration files.
- Frontend test script: none is configured in `frontend/package.json`.
- `git diff --check`: passed.

## Initial sign-off status (before backend reload)

The source-level integration is in place and isolated regression checks pass,
but Phase 8.2A/B/C is not ready for a Git checkpoint. First run/reload the
backend from this workspace so its OpenAPI exposes `/safety-cases` and
`/safety-cases/{observation_id}`, then repeat authenticated, read-only populated
case and drawer verification. No case lifecycle mutation is needed for that
sign-off.

## Runtime resolution and final connected verification

The listener investigation confirmed that PID 35556 was the SafeSite backend
started from this same workspace with `scripts/start_local_backend.ps1`. Its
OpenAPI lacked both safety-case routes because it was still serving an app
instance loaded before the Phase 8.2A routes were present. Windows initially
denied process command-line inspection; after read-only process inspection
confirmed the executable, workspace command and owner, only that verified stale
SafeSite process was stopped. The current workspace startup script then started
one backend (PID 40476). No unrelated process was stopped.

The startup script derives its database URL through `local_database_url()`,
which targets local PostgreSQL database `safesite_local`; it does not invoke
account bootstrap or migrations. The script sets a fresh ephemeral JWT secret,
so the existing Safety Officer session needed one sign-in on the same
`127.0.0.1:5173` origin. No credentials or token were logged.

Runtime API checks passed: `GET /health` returned 200, OpenAPI now lists
`GET /safety-cases` and `GET /safety-cases/{observation_id}`, unauthenticated
case access returned 401, and authenticated list/detail requests returned
JSON with 200. Before/after authenticated read-only snapshots matched exactly,
including observation IDs and count (27), alert IDs and count (13), alert
statuses and lifecycle timestamps, assessment history, and case grouping.
There are 10 unique cases for 13 alerts. Status counts are 5 Open,
1 Acknowledged, 5 Resolved and 2 Dismissed; six alerts are unresolved.

The populated register rendered all 10 case cards and distinguished case
counts from alert counts. Three cases have two child alerts. Case
`img-obs-b47667bb` contains alert #12 Acknowledged and #13 Dismissed; its case
status is Acknowledged with one unresolved alert, separately from its Critical
75 overall risk. `img-obs-6cddc5cd` contains two Open alerts and Critical 80.
All individual alert rows, their immutable risk snapshots and lifecycle
timestamps remained visible. Review-required count is zero in current live
data, so a live review marker could not be demonstrated; isolated tests cover
review-required lineage.

Original and annotated evidence for `img-obs-b47667bb` loaded at 750x360.
All case thumbnails loaded; the last lazy thumbnail loaded after scrolling it
into view. The detail drawer exposed findings, assessment versions #39–41,
decision context, individual alert actions and correction history when present.
Its link opened
`#incidents?observation_id=img-obs-b47667bb&assessment_id=39`; browser Back
returned to `#alerts`.

Connected filter checks passed: searching `img-obs-b47667bb` returned one case
and two alerts; Zone A returned one case and two alerts; Open returned four
cases and five alerts; the Nov 9 date range returned one case and one alert.
Oldest sorting began with `img-obs-3b49bec7`; newest began with
`img-obs-8453a91a`. With 10 current cases, the UI displayed exactly 10 at a
page size of 10 and disabled Next. Read-only API pagination at offsets 0, 4
and 8 returned 4, 4 and 2 unique cases; each case's child alerts stayed
together.

Keyboard checks confirmed that the case drawer and nested image preview keep
focus inside, Escape closes them, and focus returns to the invoking control.
At 390, 768 and 1280 pixel widths, neither the register nor an open mobile
drawer had horizontal overflow. No lifecycle action or other write request was
issued.

## Final verification and sign-off

- Focused isolated backend regressions: 43 tests passed across
  `test_safety_cases`, `test_alert_api`, `test_alert_policy_persistence`,
  `test_auth` and `test_persistence`. These cover authenticated/unauthorized
  access, forward-only Open → Acknowledged → Resolved transitions, dismissal,
  timestamps/history preservation, invalid transitions, idempotent alert
  handling and mixed case-state aggregation. No real alert was mutated.
- Full isolated backend suite previously passed: 219 passed, 9 PostgreSQL
  integration tests skipped because no test database was configured.
- Frontend TypeScript/Vite build passed.
- Frontend lint passed with six existing warnings outside the safety-case
  integration files.
- No frontend test script is configured.
- `git diff --check` passed.

The selected child alert ID is used for lifecycle requests, successful changes
refresh the list and selected case, and API failures remain visible without
optimistic status changes (code path inspected; mutation was intentionally not
executed against `safesite_local`). The current local dataset has no
review-required alert or `mixed_closed` case; those branches remain covered by
isolated tests. No observation, assessment, alert, user, image, model weight,
database schema, or baseline ref changed. Phase 8.2A/B/C is ready for sign-off;
no Phase 8.3 work, staging or commit was performed.

## Phase 8.2D final quality audit — 2026-11-14

The authenticated Alert Register was inspected again without issuing lifecycle
mutations. It rendered 10 observation cases and 13 individual alerts. Case
status, overall observation risk, alert count, and unresolved child count are
separate in the cards. The Acknowledged/Dismissed mixed-child case remains
Acknowledged with one unresolved alert; the two-Open case remains Open with two
unresolved alerts. The summary distinguishes filtered case/alert totals from
unresolved/review-required totals on the currently loaded page. Existing
review-required and `mixed_closed` states remain unavailable in live data.

The implementation audit found no confirmed Phase 8.2 defect requiring a code
change. Grouping remains read-time by observation ID, status aggregation uses
the documented conservative rules, and pagination occurs after grouping.
Individual actions carry the child `alert_id`; the backend keeps the existing
forward-only transition policy; successful actions refetch both list and
selected case; failures do not optimistically change status. No case-level
bulk action exists. Lifecycle paths were inspected and covered by existing
isolated tests, but no live action was submitted.

Current regression results: full isolated backend suite **219 passed, 9
PostgreSQL integration tests skipped** because `TEST_DATABASE_URL` is not
configured; TypeScript/Vite production build passed; frontend lint passed with
six warnings outside the new Safety Case components; the frontend package has
no test script; `git diff --check` passed. Connected read-only data remains 27
observations, 13 alerts and 10 cases as in the preceding API snapshots. No
saved records or evidence were written by this verification.

No additional UI defect was confirmed. Live review-required and `mixed_closed`
examples remain unavailable; isolated tests cover those branches. Phase
8.2A/B/C is ready for a Git checkpoint, and Phase 8.2 can close after checkpoint
approval. No staging or commit was performed.
