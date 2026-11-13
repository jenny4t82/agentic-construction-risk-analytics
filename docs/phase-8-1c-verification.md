# Phase 8.1C verification — 2026-11-09

**Connected verification completed with defects and explicit coverage limits.**
Clean A/B/C checkpoint sign-off is not recommended until the four defects below
are corrected and rechecked. This run makes no production-code changes.
Branch remains `revamp/milestone-2`. Existing A/B changes were preserved.

The initial attempt was blocked by an unauthenticated shared browser. After the
user signed in, the resumed run independently verified the local Safety Officer
session at `http://localhost:5173`. The API returned HTTP 200 application/json,
25 observations, 44 completed assessments and 13 alerts. GET response snapshots
of all 25 observations (including assessments/metadata) and all 13 alerts were
identical before and after browser checks. No saved data or image was modified.

## Verification matrix

| Behavior | Connected result | Coverage limits |
| --- | --- | --- |
| Risk tabs | Pass: All 25, Pending 0, Critical 2, High 10, Moderate 16, Low 12. Matching rows and stable facets checked for every tab; mixed-risk sibling bands retained | Non-empty Pending unavailable in saved data; covered by isolated tests |
| Observation ID search | Pass: img-obs-8453a91a returns exactly one matching row; clearing restores results | Exact match, not substring search |
| Work area | Pass: Zone A 4, B 10, C 5, D 4; all returned rows matched area | Two observations have no assigned area |
| Start/end dates | Pass: start 2026-11-08 returns 3; adding end 2026-11-09 returns the two November 8 observations | Date-only controls send UTC ISO bounds; local-midnight boundary semantics not separately certified |
| Newest/oldest | Pass: newest img-obs-8453a91a; oldest img-obs-f9ad6f84 | Compared with complete backend result order |
| Pagination/page size | Pass: page two has 5 rows at offset 20, Next disabled; Previous works. Sizes 10/50/20 return 10/25/20 rows and reset offset | Deep-link cleanup defect can add an extra pinned row, below |
| Expand/collapse | Pass: Enter opens and Space collapses focused observation row | Broader assistive-technology audit not performed |
| Original/annotated previews | Pass: original and overlay for img-obs-8453a91a both decode at width 750; both enlarged previews open and close via button | Keyboard modal defect below; not every image file was individually inspected |
| Deep links | Pass for off-page img-obs-225d4593, assessment 9: loads, expands, scrolls and focuses target | Invalid target and cleanup defects below; no saved pending target exists |
| Sidebar | Pass: 80px collapsed/288px expanded on Overview, AI Safety Analysis, Safety Incidents, Alert Register, Zone Analytics, Recurrence Analytics and Reports. Collapse survives reload. Mobile menu opens, closes and navigates all seven pages | Mobile keyboard defect below |
| Responsive/keyboard | No horizontal document overflow on Incidents at 1440/768/390px; all seven pages checked at 390px. Native filter controls and row keyboard activation work | Sampled geometry, not a comprehensive visual/screen-reader audit; keyboard defects below |
| Assessment editing | 58-test isolated suite passes correction, validation, stale/no-op, audit, rollback, RBAC/auth and policy cases | No live edits; PostgreSQL simultaneous row-lock scheduling untested |
| Alerts/reconciliation | Alert Register loads; 6 open, 5 resolved, 1 dismissed, 1 acknowledged. Complete alert responses unchanged after checks | No review-required live alert exists; reconciliation states covered by isolated tests |

Assessment counts differ correctly from observation tab counts: Low 12, Moderate
19, High 11, Critical 2, Pending 0. Observations can contribute to several tabs.

## Confirmed defects (left unchanged for this read-only verification)

1. **Image dialog keyboard handling:** opening an enlarged image leaves focus on
   the underlying Enlarge button outside the dialog. Escape leaves the dialog
   open. Mouse/close-button operation succeeds. Source:
   [ObservationEvidenceViewer.tsx](../frontend/src/components/ObservationEvidenceViewer.tsx).
2. **Invalid assessment deep link is silent:**
   `#incidents?observation_id=img-obs-225d4593&assessment_id=999999` displays no
   invalid/missing-assessment error and has no matching focus target. Source:
   [ObservationHistory.tsx](../frontend/src/components/ObservationHistory.tsx).
3. **Pinned observation survives clearing the deep link:** after loading that
   off-page observation, navigating back to plain `#incidents` leaves it pinned,
   producing 21 observation rows with a 20-row page setting. The pinned state
   disappears after a full reload. Same source as defect 2.
4. **Mobile navigation keyboard handling:** at 390px with navigation closed,
   Shift+Tab from Open navigation focuses the off-screen Reports button. Escape
   also fails to close the open menu. Pointer navigation works. Source:
   [AppShell.tsx](../frontend/src/components/AppShell.tsx).

## Tests and changes

Added one regression in [test_assessment_context.py](../backend/tests/test_assessment_context.py):
repeated corrections across open, acknowledged, resolved and dismissed alerts
preserve IDs/references, original band, message, status and lifecycle timestamps.
Original assessment snapshots remain intact; persisted audits grow, stale requests
fail, and alert counts do not increase. Fixtures are isolated in-memory SQLite.
An initial fixture mismatch compared timezone-aware memory values with SQLite's
timezone-naive reloaded values; reloading both sides resolved it. No production
defect was established, and application code was not modified this run.

With `DATABASE_URL` and `TEST_DATABASE_URL` explicitly empty:

```text
.venv-yolo/Scripts/python.exe -m unittest backend.tests.test_assessment_context backend.tests.test_observation_api backend.tests.test_alert_api backend.tests.test_alert_policy_persistence backend.tests.test_auth backend.tests.test_decision_engine
```

- **58 tests passed**, including nine assessment-context tests.
- `npm.cmd run build`: TypeScript/Vite passed.
- `npm.cmd run lint`: exit 0, seven pre-existing warnings in the redesigned frontend.
- Editor diagnostics: no errors in the modified test.
- `git diff --check`: passed, Windows line-ending notices only.

No saved observations, assessments, alerts or images were changed. No staging,
commits, pushes, resets, stashes or branch switches. Phase 8.1D was not started.

## Previous connected-pass conclusion

The authentication blocker is resolved and the connected verification pass is
complete. Phase 8.1C has recorded findings rather than a clean acceptance result.
Fix and recheck the four confirmed frontend defects before a verified A/B/C
checkpoint. Non-empty Pending and review-required live states remain explicitly
unverified because constructing them would change the user's data. No 8.1D work
or Git mutations were performed. Only verification documentation changed in the
resumed read-only run; existing implementation and tests were preserved.

## Four-defect correction pass — 2026-11-09

Branch confirmed `revamp/milestone-2`; all pre-existing uncommitted work retained.
Only frontend corrections and these handover documents changed in this pass.

| Defect | Root cause | Implemented correction | Connected retest |
| --- | --- | --- | --- |
| Image keyboard handling | Overlay had no focus lifecycle or Escape listener | Shared focus entry/trap/restoration, Escape, inert background, named dialog in body portal, keyboard-operable image buttons | Unverified: signed out |
| Mobile navigation | CSS translation hid links visually only | Closed mobile aside inert; open named modal traps focus, Escape/close/destination restores trigger; media query preserves desktop sidebar | Unverified at desktop/tablet/mobile |
| Invalid assessment links | Displayed history never checked membership | Validate observation and assessment; distinguish absent assessment from another observation; never focus mismatched ID; return-to-history button; exact historical target is read-only | Unverified with saved targets |
| Stale pinned record | Hash handler had no clearing branch; prepended record to page | Hash changes clear target/error/expansion; generation guard rejects stale lookups; separate labeled linked section outside untouched paginated list; no duplicate if target already in page | Unverified removal/Back/Forward |

The paginated list continues to contain only backend results, at its selected
limit. An active off-page link intentionally shows one additional detail section
labeled **Linked observation — outside the paginated results below**. This is
not counted as a page row. Returning to history preserves other URL parameters
and current filter state while removing both target parameters.

Build/TypeScript passed; lint passed with the same seven existing warnings and
no new warnings; editor diagnostics found no errors; `git diff --check` passed
(Windows line-ending notices only). 58 isolated backend tests passed with both database URL
variables empty. No live database mutation was performed. The authenticated
browser session available in the earlier matrix is no longer present: this pass
observed `#login` and requested sign-in. Prior connected successes remain prior
evidence, not a post-fix regression result. Image mouse/keyboard, mobile focus,
valid/missing/mismatched links, removal and browser history, pagination, filter
cards, desktop collapse and visual regression checks all require connected
retesting. Non-empty live Pending/review-required states and PostgreSQL locking
remain outside this pass's verified coverage.

**Status: fixes implemented, sign-off incomplete; not yet ready for a verified
combined A/B/C checkpoint.** No Phase 8.1D/8.2 or Git mutations.

## Final authenticated post-fix sign-off — 2026-11-09

This section supersedes the pending sign-off above. The shared integrated browser
was authenticated as the local Safety Officer. Branch remained
`revamp/milestone-2`. No implementation changes were needed in this final pass.

The current database contained **26 observations**, including one Pending
assessment, and **13 alerts**. This differs from the earlier 25-observation
snapshot before this pass. Full observation-query responses (including assessment
metadata) and alert responses were captured before testing and compared after:
both were identical. Only GET data requests and local UI navigation were used;
no edits, saves, account operations or alert lifecycle actions were performed.

| Focused check | Final result / evidence |
| --- | --- |
| Original and annotated previews | PASS: both loaded 750px-wide evidence; mouse and keyboard opening and mouse close/backdrop close worked |
| Image modal keyboard accessibility | PASS: focus entered named dialog; Tab and Shift+Tab stayed inside; root background inert; Escape closed both variants and restored their exact trigger |
| Closed mobile menu | PASS at 390px and 768px: sidebar inert; reverse Tab from menu trigger did not enter hidden navigation |
| Open mobile menu | PASS at both widths: focus entered; repeated Tab/Shift+Tab stayed inside; Escape restored trigger; destination click closed menu and restored trigger |
| Mobile close controls | PASS: close button and backdrop close; keyboard Enter opens menu; no horizontal document overflow at sampled widths |
| Valid off-page assessment link | PASS: `img-obs-f9ad6f84`, assessment `6`, expanded and focused exactly once in the separate linked section; paginated list remained 20 rows |
| Valid in-page assessment link | PASS: `img-obs-8453a91a`, assessment `49`, focused exactly once; no supplemental section or duplicate row |
| Missing assessment | PASS: assessment `999999` returned an explicit not-found message; no assessment focused |
| Mismatched assessment | PASS: assessment `49` paired with `img-obs-f9ad6f84` reported that it belongs to another observation; no unrelated focus |
| Missing observation | PASS: nonexistent observation returned a useful not-found message; return-to-history available |
| Clearing and Back/Forward | PASS: return cleared supplemental state; Back restored exact target; Forward removed it; page remained 20 rows |
| Unrelated navigation | PASS: navigating to Overview and back left zero supplemental records and zero expanded observation cards |
| Pagination / uniqueness | PASS: limits 10/20 yielded 10/20 unique rows; limit 50 yielded all 26 available unique records; page two at limit 20 showed six records; Previous restored 20 |
| Risk filters | PASS: Pending 1, Critical 2, High 11, Moderate 16, Low 12; All 26 with first page 20; displayed rows matched backend results |
| Thumbnails / expandable cards | PASS: 19 image thumbnails present on sampled first page all loaded; evidence card expanded and collapsed |
| Desktop sidebar | PASS at 1440px: collapse reached 80px, expand restored 288px; navigation remained usable; no horizontal document overflow |

One automated backdrop click initially targeted the scrollbar gutter outside
the backdrop's actual width and timed out. Repeating inside the visible backdrop
passed; this was a test-coordinate issue, not an application regression.

No confirmed regressions remain in the four-fix scope. The error messages include
a generic observation-load prefix even for assessment failures, but their specific
not-found/mismatch explanation is present and actionable. No code change was
needed. This focused pass does not certify every browser, screen reader or screen
size, historical-assessment-version links, or live review-required alert rendering.
PostgreSQL concurrent locking remains outside the isolated SQLite coverage.
The live Pending filter is now verified; completing it was deliberately not tested.

Previously completed validation remains applicable: 58 isolated backend tests,
frontend build/TypeScript, lint with seven existing warnings. These suites were
not repeated for this documentation-only pass. `git diff --check` was rerun.

**Phase 8.1C focused sign-off is complete. Combined Phase 8.1A/B/C is ready for a
Git checkpoint within the documented coverage. Nothing staged or committed;
Phase 8.1D was not started.**

## Multi-Pending follow-up — 2026-11-09

The analysis page previously cleared `latestAssessment` on the first completion,
unmounting the block containing all remaining forms. History refresh also hid and
unmounted rows, losing form drafts and image object URLs. Analysis now reuses the
persisted observation card outside the transient analysis-result block. History
refreshes completion results in the background. Confirmed completion responses
update each assessment locally while persisted data reloads; other forms and
evidence stay mounted. Focus advances within that observation to its next Pending
form. Progress reports completed/current assessments and remaining work. Final
observation decision is withheld while any current finding remains Pending.

A session-storage observation ID (no image/token/context payload) lets analysis
reload its saved observation after refresh. History and existing deep links recover
through the same persisted APIs. New upload/clear resets the recovery target.
Completion has an immediate in-flight/success guard against repeated submissions;
backend completion conflicts and alert policy remain unchanged. Existing recorded
context cannot be replaced by completion; editable fields retain drafts, display
recorded values, and explain the existing Edit Context correction workflow.
Unsubmitted drafts survive the completion refresh, but are not saved across a full
browser reload; persisted context and remaining Pending assessments are recovered.

### Isolated write verification

- Added an in-memory SQLite test with two synthetic Pending findings. Helmet
  completion with people=12, duration=5, repetition=1 produces High (60), leaves
  Vest Pending, and GET queries recover both statuses. Completing Vest preserves
  the first score and evidence metadata, records two audits, and reaches a final
  decision. Repeating either completion returns 409 without increasing alert count.
- Separate browser fixture used synthetic observation/assessment IDs with all
  non-GET requests intercepted or aborted. Completing the first finding retained
  High (60), moved focus to the next form, retained its entered 12/5/1 values and
  original image object URL, and displayed 1 of 2 completed / 1 remaining.
- Reload recovered the remaining form and confirmed score. Both original and
  annotated evidence loaded (2752px); evidence reads were GET-only. Two immediate
  submits for the last form caused only one request (two total for two findings).
  No forms remained and the final decision appeared only after both completed.
  Fixture state was cleared and its page navigated to about:blank afterward.
- These browser responses were simulated; actual scoring/persistence/alert
  duplicate protection was verified separately by the SQLite test, not the mock.
- 59 focused backend tests passed with DATABASE_URL and TEST_DATABASE_URL empty.
  Build/TypeScript passed; lint passed with the same seven warnings. Initial test
  fixture assumptions were corrected to the real reference inputs and SQLite's
  timezone round-trip behavior. No production scoring changes were made.

### Connected read-only verification

- Real `img-obs-1852c096` still shows Helmet #50 High (60), Vest #51 Pending,
  one remaining form with recorded 12/5/1 context, and 1 of 2 completed progress.
- Full browser refresh recovered that same state through the existing deep link.
- Full observation-query and alert responses matched before/after: **26
  observations and 13 alerts preserved**. No real completion requests were sent.
- One background health GET reported browser network suspension; the subsequent
  observation and alert GET comparisons succeeded. No app regression established.

No live write verification was performed. PostgreSQL locking and existing
cross-browser/screen-reader limitations remain. Phase 8.1D was not started;
no staging, commits, branch switching or other forbidden Git operations occurred.
