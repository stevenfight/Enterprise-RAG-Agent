@echo off
chcp 65001 >nul
echo ============================================================
echo   RAG Agent - Financial Report Analysis
echo   Starting backend and frontend services...
echo ============================================================

cd /d "%~dp0"

:: Check python
echo [CHECK] Detecting python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] python not found. Please install Python and add to PATH.
    pause
    exit /b 1
)
for /f "tokens=*" %%p in ('python --version 2^>^&1') do echo [CHECK] Python: %%p

:: Check npm
echo [CHECK] Detecting npm...
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] npm not found. Please install Node.js and add to PATH.
    pause
    exit /b 1
)
for /f "tokens=*" %%p in ('npm --version 2^>^&1') do echo [CHECK] npm: v%%p

echo.
echo [START] Launching backend (minimized)...
start "RAG-Agent Backend" /min cmd /k "chcp 65001 >nul & title RAG-Agent Backend & cd /d %CD% & python -m uvicorn src.api_service:app --host 0.0.0.0 --port 8000 --log-level info"

echo [START] Waiting for backend (3s)...
timeout /t 3 /nobreak >nul

echo [START] Launching frontend (minimized)...
start "RAG-Agent Frontend" /min cmd /k "chcp 65001 >nul & title RAG-Agent Frontend & cd /d %CD%\frontend & npm run dev"

echo [START] Waiting for frontend (8s)...
timeout /t 8 /nobreak >nul

echo [START] Opening browser...
start "" "http://localhost:5173"

echo.
echo ============================================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo ============================================================
echo.
echo   Backend & Frontend windows are minimized to taskbar.
echo   PRESS ANY KEY HERE TO STOP ALL SERVICES.
echo.
pause >nul

:: Stop backend and frontend
taskkill /fi "WINDOWTITLE eq RAG-Agent Backend*" /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq RAG-Agent Frontend*" /f >nul 2>&1

echo.
echo [STOP] All services stopped.
pause
