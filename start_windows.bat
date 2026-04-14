@echo off
title AgentCompany — CEO Server
color 0B
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

echo.
echo  ============================================================
echo   AgentCompany — CEO Dashboard Server
echo  ============================================================
echo   Dashboard:  http://localhost:8000
echo   Stop:       Press CTRL+C in this window
echo  ============================================================
echo.

cd /d "%~dp0"

:: Kill any process already using port 8000
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo  Freeing port 8000 (PID %%a)...
    taskkill /F /PID %%a >nul 2>&1
)

echo  Starting server...
echo.

venv\Scripts\python.exe -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload

echo.
echo  Server stopped.
pause
