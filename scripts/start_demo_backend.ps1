$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DemoPython = Join-Path $ProjectRoot '.venv-yolo\Scripts\python.exe'
$DemoWeights = Join-Path $ProjectRoot 'weights\best.pt'
if (-not (Test-Path -LiteralPath $DemoPython)) { throw 'The local YOLO Python environment is missing.' }
if (-not (Test-Path -LiteralPath $DemoWeights)) { throw 'The local YOLO checkpoint is missing.' }

Set-Location -LiteralPath $ProjectRoot
& $DemoPython -c "import os,secrets,uvicorn; from backend.app.bootstrap_demo_accounts import local_demo_database_url; os.environ['DATABASE_URL']=local_demo_database_url(); os.environ['SAFESITE_JWT_SECRET']=secrets.token_urlsafe(48); os.environ['YOLO_AUTOINSTALL']='False'; os.environ['HAZARD_DETECTOR_WEIGHTS']=os.path.abspath('weights/best.pt'); os.environ.pop('HAZARD_DETECTOR_MODE',None); uvicorn.run('backend.app.main:app',host='127.0.0.1',port=8000)"
