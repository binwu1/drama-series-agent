# Drama Series Agent launcher (Windows PowerShell)
# Origin host: Pixelle-Video-v0.1.15-win64 (start.bat -> streamlit) -> this repo is the new home.
# Usage:
#   .\start.ps1
#   .\start.ps1 -WithWeb
#   .\start.ps1 -Host 127.0.0.1 -Port 8000 -SkipInstall

[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$WithWeb,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:DRAMA_SERIES_ROOT = $Root
if (-not $env:COMFYUI_URL) {
    $env:COMFYUI_URL = "http://127.0.0.1:8188"
}

# Load .env if present (KEY=VALUE lines)
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
    $env:DRAMA_SERIES_ROOT = $Root
}

function Get-ProjectPython {
    $venvUnix = Join-Path $Root ".venv\bin\python"
    $venvWin = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $venvWin) { return $venvWin }
    if (Test-Path $venvUnix) { return $venvUnix }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($cmd3) { return $cmd3.Source }
    throw "Python not found. Create a venv: python -m venv .venv; .\.venv\Scripts\pip install -e `".[render,dev]`""
}

$Python = Get-ProjectPython

if (-not $SkipInstall) {
    & $Python -c "import fastapi, uvicorn" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Setup] Installing package (editable)..."
        & $Python -m pip install -e ".[render,dev]"
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    }
}

Write-Host "========================================"
Write-Host "  Drama Series Agent"
Write-Host "========================================"
Write-Host "  Root:  $env:DRAMA_SERIES_ROOT"
Write-Host "  API:   http://${HostAddress}:${Port}"
Write-Host "  Docs:  http://${HostAddress}:${Port}/docs"
Write-Host "  Comfy: $env:COMFYUI_URL"
Write-Host "  Ctrl+C to stop"
Write-Host "========================================"
Write-Host ""

$webProc = $null
try {
    if ($WithWeb) {
        # On Windows, npm is npm.cmd — Start-Process cannot launch the bare "npm" shim.
        $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if (-not $npmCmd) {
            Write-Host "[WARN] npm.cmd not found; skipping web"
        }
        else {
            $webDir = Join-Path $Root "web"
            $viteCmd = Join-Path $webDir "node_modules\.bin\vite.cmd"
            # -SkipInstall only skips Python; web still needs local vite or npm run fails.
            if (-not (Test-Path $viteCmd)) {
                Write-Host "[Setup] web deps missing; npm install in web/..."
                $npmCache = Join-Path $env:LOCALAPPDATA "npm-cache"
                New-Item -ItemType Directory -Force -Path $npmCache | Out-Null
                Push-Location $webDir
                try {
                    & npm.cmd install --cache $npmCache
                    if ($LASTEXITCODE -ne 0) { throw "npm install failed in web/" }
                }
                finally { Pop-Location }
            }
            if (-not (Test-Path $viteCmd)) {
                throw "vite not found after npm install: $viteCmd"
            }
            Write-Host "[Starting] Vite web workbench..."
            $webProc = Start-Process -FilePath "cmd.exe" `
                -ArgumentList "/c", "`"$($npmCmd.Source)`"", "run", "dev" `
                -WorkingDirectory $webDir `
                -PassThru -NoNewWindow
        }
    }

    Write-Host "[Starting] FastAPI..."
    & $Python (Join-Path $Root "scripts\run_api.py") --host $HostAddress --port $Port
}
finally {
    if ($webProc -and -not $webProc.HasExited) {
        # Kill cmd + child node/vite tree
        & taskkill.exe /PID $webProc.Id /T /F 2>$null | Out-Null
    }
}
