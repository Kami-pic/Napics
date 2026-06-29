@echo off
title NAS Media Manager - Stop Frontend & Backend
echo ========================================
echo   Stopping Frontend + Backend only
echo   (Alist/qB/Prowlarr not affected)
echo ========================================
echo.

echo [1/2] Stopping Frontend (node)...
taskkill /f /im node.exe >nul 2>&1
echo     Done

echo [2/2] Stopping Backend (uvicorn/python)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
echo     Done

echo.
echo   Frontend + Backend stopped.
echo ========================================
