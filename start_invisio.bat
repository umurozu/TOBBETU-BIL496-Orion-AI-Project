@echo off
title Invisio Startup Script

echo.
echo ==================================================
echo         INVISIO AI EDITOR - STARTUP SCRIPT
echo ==================================================
echo.

echo [0/3] Cleaning up existing instances...
taskkill /FI "WINDOWTITLE eq Invisio Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Invisio Frontend*" /T /F >nul 2>&1
echo OK: Previous services terminated.
echo.

echo [1/3] Starting Database (Docker Persistence Layer)...
echo (This will run in the background)
start "Invisio Database" /min cmd /c "cd /d %~dp0database && (docker compose up -d --remove-orphans || docker-compose up -d --remove-orphans) && exit"
echo OK: Database startup initiated.
echo.

echo [2/3] Starting Backend (FastAPI)...
start "Invisio Backend" cmd /k "title Invisio Backend && cd /d %~dp0backend && venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
echo OK: Backend starting in a new terminal.
echo.

echo [3/3] Starting Frontend (React)...
start "Invisio Frontend" cmd /k "title Invisio Frontend && cd /d %~dp0 && npm run dev"
echo OK: Frontend starting in a new terminal.
echo.

echo ==================================================
echo All services are being launched!
echo.
echo - Frontend: http://localhost:5173
echo - Backend API: http://localhost:8000/docs
echo.
echo NOTE: If Docker is not installed or running, 
echo the app will still start but DB features may skip.
echo ==================================================
echo.
echo Press any key to exit this window...
pause >nul
