@echo off
title NAS Media Manager - Stopping Services
echo ========================================
echo   NAS Media Manager - Stopping Services
echo ========================================
echo.

echo [1/5] Stopping Frontend (node)...
taskkill /f /im node.exe >nul 2>&1
echo     Done

echo [2/5] Stopping Backend (uvicorn/python)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
echo     Done

echo [3/5] Stopping Alist...
taskkill /f /im alist.exe >nul 2>&1
echo     Done

echo [4/5] Stopping qBittorrent...
taskkill /f /im qbittorrent.exe >nul 2>&1
echo     Done

echo [5/5] Stopping Prowlarr...
net stop Prowlarr >nul 2>&1
taskkill /f /im Prowlarr.exe >nul 2>&1
echo     Done

echo.
echo ========================================
echo   All services stopped!
echo ========================================
pause
