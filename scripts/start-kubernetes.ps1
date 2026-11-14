[CmdletBinding()]
param([switch]$SkipBuild, [int]$Cpus = 4, [int]$MemoryMB = 12288)
$ErrorActionPreference = 'Stop'
$labRoot = Split-Path -Parent $PSScriptRoot
$labProfile = 'llm-inference-lab-gpu'
$labPreviousKubeconfig = $env:KUBECONFIG
$labPreviousMinikubeHome = $env:MINIKUBE_HOME
function Invoke-LabCommand {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Command failed: ' + $Executable) }
}
Push-Location $labRoot
try {
    New-Item -ItemType Directory -Force -Path .local | Out-Null
    $env:MINIKUBE_HOME = Join-Path $labRoot '.local/minikube'
    $env:KUBECONFIG = Join-Path $labRoot '.local/kubeconfig'
    $labMinikubeCommand = Get-Command minikube -ErrorAction SilentlyContinue
    $labMinikube = if ($labMinikubeCommand) { $labMinikubeCommand.Source } else { Join-Path $labRoot '.local/bin/minikube.exe' }
    if (-not (Test-Path -LiteralPath $labMinikube)) { throw 'Install Minikube or place minikube.exe in .local/bin.' }
    if (-not (Test-Path -LiteralPath .local/api-token)) {
        $labBytes = New-Object byte[] 32
        $labRandom = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $labRandom.GetBytes($labBytes) } finally { $labRandom.Dispose() }
        [IO.File]::WriteAllText((Join-Path $labRoot '.local/api-token'), [Convert]::ToBase64String($labBytes))
    }
    [IO.File]::WriteAllText((Join-Path $labRoot '.local/hf-token'), [string]$env:HF_TOKEN)
    if (-not $SkipBuild) { Invoke-LabCommand 'docker' @('compose', 'build') }
    Invoke-LabCommand $labMinikube @('start', '--profile', $labProfile, '--driver=docker', '--container-runtime=docker', '--gpus=all', '--base-image=gcr.io/k8s-minikube/kicbase:v0.0.51', '--preload=false', ('--cpus=' + $Cpus), ('--memory=' + $MemoryMB), '--kubernetes-version=v1.37.0', '--keep-context')
    if ($env:OS -eq 'Windows_NT') { Invoke-LabCommand 'python' @('scripts/configure_wsl_gpu.py') }
    Invoke-LabCommand $labMinikube @('image', 'load', '--profile', $labProfile, 'llm-inference-lab-downloader:dev', 'llm-inference-lab:dev')
    Invoke-LabCommand 'kubectl' @('--context', $labProfile, 'apply', '-f', 'k8s/base/namespace.yaml')
    $labSecret = @{
        apiVersion = 'v1'; kind = 'Secret'; type = 'Opaque'
        metadata = @{ name = 'vllm-secrets'; namespace = 'llm-inference-lab' }
        stringData = @{ 'api-token' = [IO.File]::ReadAllText((Join-Path $labRoot '.local/api-token')).Trim(); 'hf-token' = [string]$env:HF_TOKEN }
    } | ConvertTo-Json -Depth 5
    $labSecret | kubectl --context $labProfile apply -f -
    if ($LASTEXITCODE -ne 0) { throw 'Secret creation failed.' }
    Invoke-LabCommand 'kubectl' @('--context', $labProfile, 'apply', '-k', 'k8s/overlays/local')
    Invoke-LabCommand 'python' @('scripts/wait_ready.py', '--context', $labProfile)
    Write-Host 'GPU deployment ready. Use .local/kubeconfig for this cluster.'
} finally {
    $env:KUBECONFIG = $labPreviousKubeconfig
    $env:MINIKUBE_HOME = $labPreviousMinikubeHome
    Pop-Location
}
