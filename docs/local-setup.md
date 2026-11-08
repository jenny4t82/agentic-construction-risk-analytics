# SafeSite local application setup

This is the normal local educational prototype environment. It uses `safesite_local` on a local PostgreSQL server and the existing YOLO checkpoint. The fresh database was verified with zero safety observations, hazards, assessments, and alerts; those records appear only after actual submissions through the application. An empty result does not establish that any site is safe.

## Prerequisites

- Local PostgreSQL, the repository's `.venv-yolo/Scripts/python.exe`, `weights/best.pt`, and frontend dependencies installed with `npm install` in `frontend/`.
- A repository-root `.env` containing a `DATABASE_URL` for the **same local PostgreSQL server**. The local scripts derive `safesite_local` from its host and credentials for their own processes. They do not rewrite `.env` or use its database name as the application database. Remote PostgreSQL hosts are refused.
- Create a database named `safesite_local` once in pgAdmin or another PostgreSQL administration tool if it does not exist. Check for an existing database first; do not replace one that already contains data. Do not copy records from `safesite_demo`.

## Migrate and create local accounts

Run from the repository root in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\migrate_local_database.ps1'
& '.\.venv-yolo\Scripts\python.exe' -m backend.app.bootstrap_local_accounts
```

The migration script runs Alembic `upgrade head` only against the verified `safesite_local` connection. Account bootstrap checks the current migration head and is idempotent: a second run reports `0 created, 3 already matched`. It refuses to overwrite a conflicting existing account.

Set `SAFESITE_LOCAL_ADMIN_PASSWORD`, `SAFESITE_LOCAL_OFFICER_PASSWORD`, and
`SAFESITE_LOCAL_USER_PASSWORD` privately in the ignored repository-root `.env`
or process environment. Each must have at least eight characters.
Identities are `admin`, `officer`, and `user` at `safesite.local`.
For existing accounts supply their current passwords; conflicting values cause
an error and never reset an account. Missing settings fail before creation.
Ordinary backend startup does not require bootstrap passwords.


These accounts are for local academic development only. Keep their passwords private. Public signup still creates only a regular user.

## Start the application

In one PowerShell terminal at the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\start_local_backend.ps1'
```

In a second terminal:

```powershell
cd frontend
npm.cmd run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/#login` and sign in as the local Safety Officer. The backend listens on `127.0.0.1:8000`; Vite proxies its API calls. The backend script targets only `safesite_local`, loads `weights/best.pt`, and generates a process-local JWT signing secret. Restarting the backend invalidates existing login tokens. The backend startup script does not run migrations automatically.

The local safety records from the earlier connected verification were cleared on 2026-11-06 while the schema and three local accounts were retained. Phase 7A subsequently submitted four existing real images through the normal persisted workflow to verify work-area editing and report filters. Those four named Phase 7A verification observations and their linked safety records were then removed from `safesite_local`; their eight owned stored image files were also removed. The current local database again has zero observations, detected hazards, risk assessments, and alerts, with all three active local accounts retained. Use **AI Safety Analysis** for fresh manual uploads. Empty results for any selected period or work area do not establish site safety.

## Preserved mentor fallback

The existing `safesite_demo` database and its prepared records remain intact. It is an optional reference environment with separate `.demo` accounts and the [mentor walkthrough](./local-mentor-demo.md). The normal local commands above do not connect to or modify it. PostgreSQL integration tests must use a separate disposable `TEST_DATABASE_URL`, never either preserved database.
