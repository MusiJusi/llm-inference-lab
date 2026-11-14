[CmdletBinding()]
param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$labRoot = Split-Path -Parent $PSScriptRoot
Push-Location $labRoot
try {
    New-Item -ItemType Directory -Force -Path .local | Out-Null
    if (-not (Test-Path -LiteralPath .local/api-token)) {
        $labBytes = New-Object byte[] 32
        $labRandom = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $labRandom.GetBytes($labBytes) } finally { $labRandom.Dispose() }
        [IO.File]::WriteAllText((Join-Path $labRoot '.local/api-token'), [Convert]::ToBase64String($labBytes))
    }
    [IO.File]::WriteAllText((Join-Path $labRoot '.local/hf-token'), [string]$env:HF_TOKEN)
    if (-not $SkipBuild) {
        docker compose build
        if ($LASTEXITCODE -ne 0) { throw 'Image build failed.' }
    }
    docker compose up --detach --wait --wait-timeout 1800
    if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Inspect docker compose ps and docker compose logs.' }
    Write-Host 'Ready: http://127.0.0.1:8001. API token: .local/api-token.'
} finally { Pop-Location }
