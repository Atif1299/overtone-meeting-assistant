# Local development starter for Overtone on Windows.
# Starts backend (8001), presenter (5175), dashboard (5176).
#
#   .\start-local.ps1              # API + UIs
#
# Ctrl+C stops everything.

param(
    [switch]$NoTunnels
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $Root "backend\.env"
$LogDir = Join-Path $Root "logs"
$script:ChildProcesses = @()

function Get-BackendPython {
    $candidates = @(
        (Join-Path $Root "backend\.venv\Scripts\python.exe"),
        (Join-Path $Root "backend\venv\Scripts\python.exe")
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

function Start-LoggedProcess {
    param([string]$FilePath, [string[]]$ArgumentList, [string]$WorkingDirectory, [string]$LogPath)
    $errPath = $LogPath + ".err"
    $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $LogPath -RedirectStandardError $errPath -PassThru -WindowStyle Hidden
    $script:ChildProcesses += $proc
    return $proc
}

function Get-NpmCmd {
    $cmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd = Get-Command npm -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "npm not found on PATH"
}

function Stop-Children {
    Write-Host ""
    Write-Host "Stopping services..."
    foreach ($proc in $script:ChildProcesses) {
        if ($proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Get-CimInstance Win32_Process -Filter ("ParentProcessId=" + $proc.Id) -ErrorAction SilentlyContinue |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        }
    }
    Write-Host "Done."
}

$python = Get-BackendPython
if (-not $python) {
    Write-Host "ERROR: backend venv not found. Run:"
    Write-Host "  cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path (Join-Path $Root "presenter\node_modules"))) {
    Write-Host "ERROR: presenter\node_modules missing. Run: cd presenter; npm install"
    exit 1
}
if (-not (Test-Path (Join-Path $Root "dashboard\node_modules"))) {
    Write-Host "ERROR: dashboard\node_modules missing. Run: cd dashboard; npm install"
    exit 1
}
if (-not (Test-Path $EnvFile)) {
    Write-Host "ERROR: backend\.env not found. Copy backend\.env.example to backend\.env and fill in keys."
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "backend\data") | Out-Null

try {
    Write-Host "Starting presenter -> http://127.0.0.1:5175  (log: logs\presenter.log)"
    $npm = Get-NpmCmd
    Start-LoggedProcess -FilePath $npm -ArgumentList @("run", "dev") -WorkingDirectory (Join-Path $Root "presenter") -LogPath (Join-Path $LogDir "presenter.log") | Out-Null

    Write-Host "Starting dashboard -> http://127.0.0.1:5176  (log: logs\dashboard.log)"
    Start-LoggedProcess -FilePath $npm -ArgumentList @("run", "dev") -WorkingDirectory (Join-Path $Root "dashboard") -LogPath (Join-Path $LogDir "dashboard.log") | Out-Null

    Write-Host "Starting backend   -> http://127.0.0.1:8001  (log: logs\backend.log)"
    Start-LoggedProcess -FilePath $python -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8001") -WorkingDirectory (Join-Path $Root "backend") -LogPath (Join-Path $LogDir "backend.log") | Out-Null

    Write-Host "Waiting for backend to be ready..."
    $healthy = $false
    for ($i = 0; $i -lt 20; $i++) {
        try {
            $res = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -UseBasicParsing -TimeoutSec 2
            if ($res.StatusCode -eq 200) { $healthy = $true; break }
        } catch {
        }
        Start-Sleep -Seconds 1
    }
    if ($healthy) {
        Write-Host "Backend healthy"
    } else {
        Write-Host "Backend not yet responding - check logs\backend.log"
    }

    Write-Host ""
    Write-Host "Local"
    Write-Host "  API docs   http://127.0.0.1:8001/docs"
    Write-Host "  Presenter  http://127.0.0.1:5175"
    Write-Host "  Dashboard  http://127.0.0.1:5176"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop all services."
    while ($true) { Start-Sleep -Seconds 3600 }
} finally {
    Stop-Children
}
