Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$PnpmVersion = if ($env:PNPM_VERSION) { $env:PNPM_VERSION } else { "10.11.0" }

function Write-Log([string]$Message) {
  Write-Host "[dev-start] $Message"
}

function Fail([string]$Message) {
  throw "[dev-start] ERROR: $Message"
}

function Ensure-Pnpm() {
  if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    return
  }
  if (Get-Command corepack -ErrorAction SilentlyContinue) {
    Write-Log "pnpm not found, trying corepack..."
    & corepack enable | Out-Null
    & corepack prepare "pnpm@$PnpmVersion" --activate | Out-Null
  }
  if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    Fail "pnpm not found. Run setup first."
  }
}

$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
  Fail "missing .venv. Run: pwsh -File scripts/dev/setup.ps1"
}

if (-not (Test-Path (Join-Path $RootDir "frontend\node_modules"))) {
  Fail "missing frontend/node_modules. Run: pwsh -File scripts/dev/setup.ps1"
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Fail "node not found. Run setup first."
}
Ensure-Pnpm

try {
  & $VenvPython -c "import fastapi, sqlalchemy, ccxt" | Out-Null
} catch {
  Fail "backend dependencies missing in .venv. Run: pwsh -File scripts/dev/setup.ps1"
}

$BackendArgs = @(
  "-m", "uvicorn", "main:app",
  "--host", "0.0.0.0",
  "--port", "8000",
  "--reload"
)
$FrontendCmd = Get-Command pnpm -ErrorAction SilentlyContinue
if (-not $FrontendCmd) {
  Fail "pnpm command not found."
}

$backendProc = $null
$frontendProc = $null

try {
  Write-Log "starting backend http://127.0.0.1:8000"
  $backendProc = Start-Process -FilePath $VenvPython -ArgumentList $BackendArgs -WorkingDirectory (Join-Path $RootDir "backend") -PassThru

  Write-Log "starting frontend http://127.0.0.1:3000"
  $frontendProc = Start-Process -FilePath $FrontendCmd.Source -ArgumentList @("--dir", "frontend", "start") -WorkingDirectory $RootDir -PassThru

  Write-Log "backend_pid=$($backendProc.Id) frontend_pid=$($frontendProc.Id)"
  Write-Log "press Ctrl+C to stop both services"

  while ($true) {
    Start-Sleep -Seconds 1
    $backendProc.Refresh()
    $frontendProc.Refresh()
    if ($backendProc.HasExited -or $frontendProc.HasExited) {
      break
    }
  }
} finally {
  if ($backendProc -and -not $backendProc.HasExited) {
    Stop-Process -Id $backendProc.Id -Force
  }
  if ($frontendProc -and -not $frontendProc.HasExited) {
    Stop-Process -Id $frontendProc.Id -Force
  }
}

if ($backendProc -and $backendProc.HasExited) {
  Write-Log "backend exited with code $($backendProc.ExitCode)"
  exit $backendProc.ExitCode
}
if ($frontendProc -and $frontendProc.HasExited) {
  Write-Log "frontend exited with code $($frontendProc.ExitCode)"
  exit $frontendProc.ExitCode
}
