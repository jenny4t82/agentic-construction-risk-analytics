$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LocalPython = Join-Path $ProjectRoot '.venv-yolo\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $LocalPython)) { throw 'The local Python environment is missing.' }

Set-Location -LiteralPath $ProjectRoot
& $LocalPython -c "import os; from sqlalchemy import create_engine,text; from alembic import command; from alembic.config import Config; from backend.app.bootstrap_local_accounts import local_database_url; url=local_database_url(); engine=create_engine(url); connection=engine.connect(); name=connection.scalar(text('SELECT current_database()')); connection.close(); engine.dispose(); assert name == 'safesite_local', 'Refusing to migrate a different database'; os.environ['DATABASE_URL']=url; command.upgrade(Config('alembic.ini'),'head')"
if ($LASTEXITCODE -ne 0) { throw 'Local migration failed.' }
