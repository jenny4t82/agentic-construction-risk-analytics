# Phase 8.3C — Evidence-Linked Recurrence Analytics

## Scope and preserved definition

Recurrence remains the same supported PPE hazard category appearing in the
same named work area across at least two distinct persisted observation IDs.
Multiple matching detections inside one observation and additional assessment
versions do not increase recurrence. Categories and areas remain separate.
Observation time, not assessment or detection time, is filtered using the
existing timezone-aware half-open interval `[start, end)`. Work-area values are
trimmed at their edges while preserving case and internal spelling/spacing;
null, blank, `unspecified`, `unknown`, and `unassigned work area` are excluded.
No worker identity, risk calculation, or accident likelihood is inferred.

## API reuse

No backend route or recurrence response was changed. The page continues to use
authenticated `GET /analytics/work-area-recurrence?start=&end=` for the
authoritative area/category groups and their distinct-observation counts.
Selecting a group reuses `GET /analytics/finding-observations` with
`work_area`, `hazard_type`, the same normalized date bounds,
`area_mode=recurrence`, deterministic newest sorting, and page size/offset.
That endpoint applies the same supported source-label/category pair check and
named-area exclusions before counting and paging unique observations. Its
response supplies observation risk, Pending/provisional state, complete
assessment lineage, evidence flags and an optional existing safety-case ID.
Image bytes continue through the existing authenticated image endpoint.

The drawer compares its distinct-observation total with the selected
recurrence group's count and displays a warning if the contracts diverge.
Pagination is over observations, not individual detections. No evidence,
assessment, alert, or observation records are written.

## UI behavior

The former text-only ID list is replaced with a responsive area/category
investigation list. Summary cards distinguish recurring area/category pairs,
work areas, the unique observation IDs represented across groups, and
supported PPE categories. Search and sort are client-side over the complete
recurrence response. Each group reports its exact distinct-observation count
and whether it is repeated or observed once; selecting it opens the shared
evidence drawer. The drawer shows per-observation overall risk separately from
the matching finding's own assessment history, thumbnails, original/annotated
previews, Safety Incidents links, and conditional Safety Case links.

The date controls preserve the existing local `datetime-local` behavior and
serialize to offset-bearing UTC instants. The API response's normalized window
is passed to the supporting-observation request. Clear Filters returns to all
history. Empty, loading, error and no-search-match states are explicit. The
shared modal focus utility provides Escape handling, focus containment and
restoration. No new dependency or scoring logic was added.

## Validation and limitations

Focused Zone and Recurrence tests passed (27 total). The full isolated backend
suite passed 227 tests; 9 PostgreSQL integration tests were skipped because no
disposable `TEST_DATABASE_URL` was configured. Frontend TypeScript/Vite build
passed. Oxlint passed with five existing warnings in unchanged files; the
updated recurrence page adds no lint warnings. `git diff --check` passed. The
recurrence aggregate remains an unpaginated in-memory summary at current scale;
only supporting observations are paginated. During Phase 8.3D, the shared
browser again resolved to `chrome-error://chromewebdata/`, while ports 8000 and
5173 had no listening SafeSite processes. Consequently, live OpenAPI/API
consistency, authenticated UI, image, accessibility, responsive behavior, and
before/after database snapshots could not be independently verified. No
services were started and no login or data mutation was attempted. See
`phase-8-3d-final-verification.md` for the combined verification record and
manual Chrome checklist.
