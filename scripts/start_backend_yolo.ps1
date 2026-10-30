$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv-yolo\Scripts\python.exe"
$Weights = Join-Path $ProjectRoot "weights\best.pt"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "The YOLO Python environment was not found at $Python"
}

if (-not (Test-Path -LiteralPath $Weights)) {
    throw "The trained checkpoint was not found at $Weights"
}

Set-Location -LiteralPath $ProjectRoot
$env:YOLO_AUTOINSTALL = "False"
$env:HAZARD_DETECTOR_WEIGHTS = (Resolve-Path -LiteralPath $Weights).Path
Remove-Item Env:HAZARD_DETECTOR_MODE -ErrorAction SilentlyContinue

& $Python -m uvicorn backend.app.main:app --reload
