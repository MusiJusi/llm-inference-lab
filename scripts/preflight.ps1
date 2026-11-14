[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
foreach ($labCommand in @('docker', 'nvidia-smi', 'python')) {
    if (-not (Get-Command $labCommand -ErrorAction SilentlyContinue)) { throw ($labCommand + ' is not available.') }
}
docker version --format '{{.Server.Version}}'
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with the WSL 2 backend.' }
docker compose version
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is unavailable.' }
nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader
if ($LASTEXITCODE -ne 0) { throw 'NVIDIA GPU is unavailable.' }
Write-Host 'Host prerequisites passed. The container GPU check is performed by scripts/check_gpu.py.'
