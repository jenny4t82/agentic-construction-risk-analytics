# SafeSite local mentor demo

This is an **optional preserved mentor fallback**, separate from the [normal local application](./local-setup.md). Its accounts are for local development only. The application records actionable alert rows; it does not send SMS, email, or push notifications.

## Before starting

- Confirm local PostgreSQL is running and the preserved `safesite_demo` database exists. Do not reset or recreate it. Its Alembic revision should be `0003_alert_dismissed_at`.
- Confirm `.venv-yolo/Scripts/python.exe`, `weights/best.pt`, and the repository-root `.env` with a **local** PostgreSQL `DATABASE_URL` are available. The demo helper derives the database name `safesite_demo` from that local connection. Do not point it at a remote server.
- From the repository root, run `& '.\.venv-yolo\Scripts\python.exe' -m backend.app.bootstrap_demo_accounts`. It creates missing demo identities, verifies existing ones, and refuses to overwrite conflicting role, password, or active state. Running it again should report `0 created, 3 already matched`.
- Start the backend in one PowerShell terminal: `powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\start_demo_backend.ps1'`. This script targets only local `safesite_demo`, supplies a process-local JWT secret and checkpoint path, and serves `http://127.0.0.1:8000`. A backend restart invalidates existing browser tokens.
- Start the frontend in another terminal: `cd frontend`, then `npm.cmd run dev -- --host 127.0.0.1`. Open `http://127.0.0.1:5173/#login`. Vite proxies API calls to port 8000.

## Demo-only credentials

Set `SAFESITE_DEMO_ADMIN_PASSWORD`, `SAFESITE_DEMO_OFFICER_PASSWORD`, and
`SAFESITE_DEMO_USER_PASSWORD` privately in the ignored repository-root `.env`
or process environment. Each must have at least eight characters.
Identities are `admin`, `officer`, and `user` at `safesite.demo`.
For existing accounts supply their current passwords; conflicting values cause
an error and never reset an account. Missing settings fail before creation.
Ordinary backend startup does not require bootstrap passwords.


The local development login page names the available roles but does not display passwords. Public signup creates only a regular user and requires a new password of at least eight characters. Existing-account login continues to check the stored hash without a new length rule.

## Reviewed image examples

These local evaluation images produced the listed results with the current checkpoint during the Phase 6E walkthrough. Use a fresh explicit observation ID for another submission; reusing the saved ID with the same bytes and inputs returns the exact-duplicate response. Set `work_area` to `Phase 6E Demo Bay` if you want the new findings grouped with this walkthrough. These model outputs are examples, not independent scene-safety or accuracy validation.

| Example | Local image | Operator context | Observed result |
|---|---|---|---|
| No supported finding | `datasets/evaluation/construction-site-safety-v1/valid/images/construction-1023-_jpg.rf.934b9e434de66c21149aaa3d2d7680c5.jpg` | No added scoring values | `no_alert`; no supported explicit PPE violation detected. |
| Pending then warning | `datasets/evaluation/construction-site-safety-v1/valid/images/-1079-_png_jpg.rf.b5df117d2f459522987e48fdf0f80564.jpg` | Upload without duration/repetition; complete the saved pending assessment with duration 10 minutes and repetition 0 | Missing Safety Vest finding; final Moderate/`warning`, no Alert. |
| Actionable alert | `datasets/evaluation/construction-site-safety-v1/valid/images/ppe_0665_jpg.rf.885665684b4ab7e7fed9393d499f3d1a.jpg` | People 10, duration 240 minutes, repetition 5 | Missing Safety Helmet and Vest findings; Critical/`alert`, two linked Alerts. |

## Mentor demo sequence

1. Sign in as Safety Officer. Show Overview and its recorded findings, risk distribution, and alert counts.
2. Open AI Safety Analysis. Use a reviewed local image and a new explicit observation ID. Explain that only supported explicit missing-PPE classes become findings; a no-finding result is not proof of site safety.
3. Show the detector confidence for each supported finding and the annotated image where available. Explain that confidence is model evidence, not severity or risk.
4. For a pending result, provide only missing people/duration/repetition context through Complete Assessment. Show the resulting score and shared `warning` or `alert` decision without re-uploading. Repetition here is operator-supplied scoring context.
5. Open Safety Incidents / Observation History to show the saved ID, images, findings, completed assessment, and decision.
6. Open Alert Register. Acknowledge then resolve one open alert. Dismiss a **different** open alert. Refresh and show the separate lifecycle timestamps. Keep other open demo alerts for later presentation.
7. Open Zone Analytics for hazard-row totals, work-area metrics, common violation, risk distribution, and open/unresolved/resolved alert counts.
8. Open Recurrence Analytics. Show a repeated canonical PPE group, distinct contributing observation IDs, all-history default, and an explicit date filter. Recurrence is informational and does not change scoring or alerts.
9. Optionally sign in as Admin to demonstrate role assignment through the protected API, and as Regular User to show read access without alert or pending-completion controls. Backend role checks remain authoritative.

## Talking points and limits

- A single image cannot establish exposure duration or historical recurrence. The Safety Officer may supply operational context; severity comes from the supported hazard policy.
- `repeated_count` is caller-supplied scoring input. Work-area recurrence counts **distinct persisted observation IDs** and does not infer a repeated worker, a site identity, an accident outcome, or an accident probability.
- `work_area` is free text. Case and spelling variants remain separate; null, blank, and `Unspecified` areas are excluded from named-area recurrence.
- The Low/Moderate warning and High/Critical alert notification mapping is provisional and awaits mentor review. It is not a regulatory or certified threshold.
- Held-out model recall and PPE-class coverage remain limited. A missing positive detection does not prove PPE is absent, and no supported explicit violation detected does not prove compliance.
- `safesite_demo` is preserved. The Phase 6E walkthrough added `phase6e-clean-1106`, `phase6e-pending-1106`, and `phase6e-alert-1106` via the normal persisted image workflow. The latter produced two alerts, one resolved and one dismissed; earlier open alerts remain available.
