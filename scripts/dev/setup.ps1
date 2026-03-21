Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$PnpmVersion = if ($env:PNPM_VERSION) { $env:PNPM_VERSION } else { "10.11.0" }
$UvInstallHint = "Install uv first: https://docs.astral.sh/uv/getting-started/installation/"

function Write-Log([string]$Message) {
  Write-Host "[dev-setup] $Message"
}

function Fail([string]$Message) {
  throw "[dev-setup] ERROR: $Message"
}

function Ensure-Command([string]$Name, [string]$Hint) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    Fail "$Name not found. $Hint"
  }
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
    Fail "pnpm not found. Install pnpm 10+ or enable corepack."
  }
}

Ensure-Command "node" "Install Node.js 20+."
Ensure-Command "uv" $UvInstallHint
Ensure-Pnpm

Write-Log "root=$RootDir"
Write-Log "uv=$(& uv --version)"
Write-Log "node=$(& node --version)"
Write-Log "pnpm=$(& pnpm --version)"

$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
  Write-Log "creating virtualenv at .venv"
  if ($env:PYTHON_BIN) {
    & uv venv --python $env:PYTHON_BIN (Join-Path $RootDir ".venv")
  } else {
    & uv venv (Join-Path $RootDir ".venv")
  }
}

if (-not (Test-Path $VenvPython)) {
  Fail "virtualenv python not found at $VenvPython"
}

Write-Log "installing backend dependencies"
& uv pip install --python $VenvPython -r (Join-Path $RootDir "backend\requirements.txt")

Write-Log "installing frontend dependencies"
& pnpm --dir (Join-Path $RootDir "frontend") install --frozen-lockfile

Write-Log "setup complete"
Write-Log "next: pwsh -File scripts/dev/start.ps1"
