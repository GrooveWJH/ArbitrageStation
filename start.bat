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
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause & exit /b 1
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
    npm install
    if errorlevel 1 (echo [ERROR] Frontend dependency install failed & pause & exit /b 1)
)

echo [4/4] Starting frontend (http://localhost:3000) ...
start "Arbitrage-Frontend" cmd /k "npm start"

echo.
echo ========================================
echo   Started!
echo   Frontend: http://localhost:3000
echo   Backend API: http://localhost:8000/docs
echo ========================================
timeout /t 3
