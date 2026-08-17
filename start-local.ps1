# Local development starter for Overtone on Windows.
# Starts backend (8000), frontend (5173), dashboard (5174).
# With tunnels (default): two cloudflared URLs are written into backend/.env
# so Recall.ai webhooks and the bot camera page are publicly reachable.
#
#   .\start-local.ps1              # full meeting flow (needs cloudflared)
#   .\start-local.ps1 -NoTunnels   # API + UIs only
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

function Set-DotEnvValue {
    param([string]$Key, [string]$Value)
    if (-not (Test-Path $EnvFile)) {
        throw "backend\.env not found. Copy backend\.env.example to backend\.env and fill in keys."
    }
    $lines = Get-Content -Path $EnvFile
    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -match ("^" + [regex]::Escape($Key) + "=")) {
            $found = $true
            ($Key + "=" + $Value)
        } else {
            $line
        }
    }
    if (-not $found) {
        $updated += ($Key + "=" + $Value)
    }
    Set-Content -Path $EnvFile -Value $updated -Encoding utf8
}

function Wait-TunnelUrl {
    param([string]$LogPath, [int]$TimeoutSeconds = 45)
    $paths = @($LogPath, ($LogPath + ".err"))
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        foreach ($path in $paths) {
            if (Test-Path $path) {
                $match = Select-String -Path $path -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($match) {
                    return $match.Matches[0].Value
                }
            }
        }
        Start-Sleep -Seconds 1
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
if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
    Write-Host "ERROR: frontend\node_modules missing. Run: cd frontend; npm install"
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
New-Item -ItemType Directory -Force -Path (Join-Path $Root "backend\presentations") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "backend\generated_audio") | Out-Null

try {
    $backendTunnel = $null
    $frontendTunnel = $null

    if (-not $NoTunnels) {
        $cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
        if (-not $cloudflared) {
            Write-Host "ERROR: cloudflared not found. Install from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ then re-run."
            exit 1
        }
        Write-Host "Starting tunnels..."
        Start-LoggedProcess -FilePath $cloudflared.Source -ArgumentList @("tunnel", "--url", "http://localhost:8000", "--no-autoupdate") -WorkingDirectory $Root -LogPath (Join-Path $LogDir "cf-backend.log") | Out-Null
        Start-LoggedProcess -FilePath $cloudflared.Source -ArgumentList @("tunnel", "--url", "http://localhost:5173", "--no-autoupdate") -WorkingDirectory $Root -LogPath (Join-Path $LogDir "cf-frontend.log") | Out-Null
    }

    Write-Host "Starting frontend  -> http://127.0.0.1:5173  (log: logs\frontend.log)"
    $npm = Get-NpmCmd
    Start-LoggedProcess -FilePath $npm -ArgumentList @("run", "dev") -WorkingDirectory (Join-Path $Root "frontend") -LogPath (Join-Path $LogDir "frontend.log") | Out-Null

    Write-Host "Starting dashboard -> http://127.0.0.1:5174  (log: logs\dashboard.log)"
    Start-LoggedProcess -FilePath $npm -ArgumentList @("run", "dev") -WorkingDirectory (Join-Path $Root "dashboard") -LogPath (Join-Path $LogDir "dashboard.log") | Out-Null

    if (-not $NoTunnels) {
        Write-Host "Waiting for tunnel URLs..."
        $backendTunnel = Wait-TunnelUrl (Join-Path $LogDir "cf-backend.log")
        $frontendTunnel = Wait-TunnelUrl (Join-Path $LogDir "cf-frontend.log")
        if (-not $backendTunnel -or -not $frontendTunnel) {
            Write-Host "ERROR: Tunnels did not start in time. Check logs\cf-backend.log and logs\cf-frontend.log"
            Stop-Children
            exit 1
        }
        Write-Host "Patching backend\.env with tunnel URLs..."
        Set-DotEnvValue "BACKEND_URL" $backendTunnel
        Set-DotEnvValue "FRONTEND_URL" $frontendTunnel
        Set-DotEnvValue "CORS_ALLOWED_ORIGINS" ("http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174," + $frontendTunnel)

        Write-Host "Updating Azure Blob CORS rules..."
        Push-Location (Join-Path $Root "backend")
        try {
            & $python (Join-Path $Root "scripts\update_blob_cors.py")
        } finally {
            Pop-Location
        }
    }

    Write-Host "Starting backend   -> http://127.0.0.1:8000  (log: logs\backend.log)"
    Start-LoggedProcess -FilePath $python -ArgumentList @("-m", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000") -WorkingDirectory (Join-Path $Root "backend") -LogPath (Join-Path $LogDir "backend.log") | Out-Null

    Write-Host "Waiting for backend to be ready..."
    $healthy = $false
    for ($i = 0; $i -lt 20; $i++) {
        try {
            $res = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
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
    Write-Host "  API docs   http://127.0.0.1:8000/docs"
    Write-Host "  Frontend   http://127.0.0.1:5173"
    Write-Host "  Dashboard  http://127.0.0.1:5174"
    if ($backendTunnel -and $frontendTunnel) {
        Write-Host ""
        Write-Host "Public (Recall webhooks)"
        Write-Host ("  Backend    " + $backendTunnel)
        Write-Host ("  Frontend   " + $frontendTunnel)
        Write-Host "  Recall webhook URL (paste in Recall dashboard):"
        Write-Host ("    " + $backendTunnel + "/api/webhook/recall/bot-status")
    }
    Write-Host ""
    Write-Host "Press Ctrl+C to stop all services."
    while ($true) { Start-Sleep -Seconds 3600 }
} finally {
    Stop-Children
}
