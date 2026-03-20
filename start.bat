@echo off
echo ========================================
echo   Arbitrage Tool - Starting...
echo ========================================

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause & exit /b 1
)

node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 20+
    pause & exit /b 1
)

pnpm --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] pnpm not found. Trying to enable via corepack...
    corepack enable >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] pnpm not found and corepack enable failed.
        echo         Please install pnpm 10+ or enable corepack manually.
        pause & exit /b 1
    )
    corepack prepare pnpm@10.11.0 --activate >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to prepare pnpm via corepack.
        pause & exit /b 1
    )
    pnpm --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] pnpm is still unavailable after corepack activation.
        pause & exit /b 1
    )
    echo [INFO] pnpm is now ready.
)

echo [1/4] Installing backend dependencies...
cd /d "%~dp0backend"
pip install -r requirements.txt -q
if errorlevel 1 (echo [ERROR] Backend dependency install failed & pause & exit /b 1)

echo [2/4] Starting backend (http://localhost:8000) ...
start "Arbitrage-Backend" cmd /k "python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

cd /d "%~dp0frontend"

echo [3/4] Installing frontend dependencies...
if not exist node_modules (
    pnpm install --frozen-lockfile
    if errorlevel 1 (echo [ERROR] Frontend dependency install failed & pause & exit /b 1)
)

echo [4/4] Starting frontend (http://localhost:3000) ...
start "Arbitrage-Frontend" cmd /k "pnpm start"

echo.
echo ========================================
echo   Started!
echo   Frontend: http://localhost:3000
echo   Backend API: http://localhost:8000/docs
echo ========================================
timeout /t 3
