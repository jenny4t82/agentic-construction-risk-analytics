$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LocalPython = Join-Path $ProjectRoot '.venv-yolo\Scripts\python.exe'
$LocalWeights = Join-Path $ProjectRoot 'weights\best.pt'
if (-not (Test-Path -LiteralPath $LocalPython)) { throw 'The local YOLO Python environment is missing.' }
if (-not (Test-Path -LiteralPath $LocalWeights)) { throw 'The local YOLO checkpoint is missing.' }

Set-Location -LiteralPath $ProjectRoot
& $LocalPython -c "import os,secrets,uvicorn; from backend.app.bootstrap_local_accounts import local_database_url; os.environ['DATABASE_URL']=local_database_url(); os.environ['SAFESITE_JWT_SECRET']=secrets.token_urlsafe(48); os.environ['YOLO_AUTOINSTALL']='False'; os.environ['HAZARD_DETECTOR_WEIGHTS']=os.path.abspath('weights/best.pt'); os.environ.pop('HAZARD_DETECTOR_MODE',None); uvicorn.run('backend.app.main:app',host='127.0.0.1',port=8000)"
