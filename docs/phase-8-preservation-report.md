# Phase 8 preservation review ? 2026-11-08

Original branch: `feature/safety-agent-visual-test`. Origin is the existing GitHub
repository. The full Milestone 2 work is retained; no scoring, alert, decision,
model, UI or database changes were introduced by this preservation phase.

## Security changes

Local/demo bootstrap passwords now come from six explicitly named private
`SAFESITE_LOCAL_*_PASSWORD` / `SAFESITE_DEMO_*_PASSWORD` variables. Bootstrap
loads the ignored root `.env` without overriding process variables, checks all
secrets before creating accounts, and refuses existing-account conflicts.
No fallback passwords exist. Database errors no longer print connection details.
Normal server startup does not run bootstrap and needs no bootstrap passwords.
`.env.example` contains placeholders only. Public docs no longer contain reusable
account passwords. No local secrets or account records were changed.

The complete Git candidate file inventory was scanned for former bootstrap
passwords, private environment secret values, private-key headers and common
token patterns. Published origin history was checked for former bootstrap
credentials and private environment values. No matches were found. Synthetic
unit-test credentials and documentation placeholders are not application accounts.
This pattern-based review does not claim exhaustive secret detection.

## Validation

The full backend suite in `.venv-yolo` passed: 199 tests run, nine disposable
PostgreSQL tests skipped. Following additional password-conflict regression
coverage, all ten focused bootstrap tests passed. Frontend build (including
TypeScript) passed. Lint exited successfully with six existing warnings.
`git diff --check` passed; Git reports Windows line-ending conversion warnings.
The lightweight `.venv` lacks declared fpdf2/langgraph dependencies; its initial
suite failed imports. Use the documented dependency install or validated YOLO
environment. No destructive database tests were run. Existing database login
was not exercised; auth unit tests passed, and password-reset behavior is absent.

## Inclusion and exclusions

Include all existing modified application source, frontend components, tests,
Alembic migrations, scripts, configuration template, small SVG branding assets,
README, handover, progress logs, mentor/architecture notes and text-based dataset
research/evaluation reports and scripts. Keep the already tracked notebook and
model-weight exclusion strategy.

Exclude private `.env`, virtual environments, datasets, model weights, uploaded
observation evidence, generated evaluation images/outputs, diagnostics, private
editor state, caches, databases, backups and generated PDFs. These local files
are retained on disk. Diagnostic source scripts are retained as implementation
records; their referenced local inputs are not published.

The original branch, preserved branch/tag and revamp branch are to point to one
validated commit. Remote ref verification and exact commit SHA are reported in
the final task response after publication; no existing refs may be overwritten.
