$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LocalPython = Join-Path $ProjectRoot '.venv-yolo\Scripts\python.exe'
$LocalWeights = Join-Path $ProjectRoot 'weights\best.pt'
$LocalEnvironmentFile = Join-Path $ProjectRoot '.env'
if (-not (Test-Path -LiteralPath $LocalPython)) { throw 'The local YOLO Python environment is missing.' }
if (-not (Test-Path -LiteralPath $LocalWeights)) { throw 'The local YOLO checkpoint is missing.' }

# Keep local JWTs valid across backend restarts. Prefer an explicit process
# environment value, then the private ignored .env file. On first local launch,
# create and persist a random development key without printing it.
$JwtSecret = [Environment]::GetEnvironmentVariable('SAFESITE_JWT_SECRET')
if ([string]::IsNullOrWhiteSpace($JwtSecret) -and (Test-Path -LiteralPath $LocalEnvironmentFile)) {
    foreach ($Line in Get-Content -LiteralPath $LocalEnvironmentFile) {
        $Line = $Line.TrimStart([char]0xFEFF)
        if ($Line -match '^\s*SAFESITE_JWT_SECRET\s*=\s*(.*?)\s*$') {
            $JwtSecret = $Matches[1]
            if (($JwtSecret.StartsWith('"') -and $JwtSecret.EndsWith('"')) -or
                ($JwtSecret.StartsWith("'") -and $JwtSecret.EndsWith("'"))) {
                $JwtSecret = $JwtSecret.Substring(1, $JwtSecret.Length - 2)
            }
            break
        }
    }
}
if ([string]::IsNullOrWhiteSpace($JwtSecret)) {
    $SecretBytes = New-Object byte[] 48
    $RandomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $RandomGenerator.GetBytes($SecretBytes) }
    finally { $RandomGenerator.Dispose() }
    $JwtSecret = [Convert]::ToBase64String($SecretBytes)
    Add-Content -LiteralPath $LocalEnvironmentFile -Value "SAFESITE_JWT_SECRET=$JwtSecret" -Encoding UTF8
}
if ($JwtSecret.Length -lt 32) {
    throw 'SAFESITE_JWT_SECRET in the local environment must be at least 32 characters.'
}
$env:SAFESITE_JWT_SECRET = $JwtSecret

Set-Location -LiteralPath $ProjectRoot
& $LocalPython -c "import os,uvicorn; from backend.app.bootstrap_local_accounts import local_database_url; os.environ['DATABASE_URL']=local_database_url(); os.environ['YOLO_AUTOINSTALL']='False'; os.environ['HAZARD_DETECTOR_WEIGHTS']=os.path.abspath('weights/best.pt'); os.environ.pop('HAZARD_DETECTOR_MODE',None); uvicorn.run('backend.app.main:app',host='127.0.0.1',port=8000)"
