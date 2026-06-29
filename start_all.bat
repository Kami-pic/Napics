@echo off
:: 全部启动：Alist + qBittorrent + Prowlarr + Backend + Frontend
:: 无窗口模式：双击时通过 VBS 隐藏自身重启

if not "%HIDDEN%"=="1" (
    set "HIDDEN=1"
    cscript //nologo "%~dp0_start_hidden.vbs" "%~f0"
    exit /b
)

cd /d %~dp0

:: Alist
tasklist /fi "imagename eq alist.exe" | find /i "alist.exe" >nul 2>&1
if errorlevel 1 (
    start /b cmd /c "cd /d %~dp0..\Alist && alist.exe server >nul 2>&1"
)
timeout /t 2 /nobreak >nul

:: qBittorrent
tasklist /fi "imagename eq qbittorrent.exe" | find /i "qbittorrent.exe" >nul 2>&1
if errorlevel 1 (
    start "" "C:\Program Files\qBittorrent\qbittorrent.exe" --no-splash
)
timeout /t 2 /nobreak >nul

:: Prowlarr（Windows 服务）
sc query Prowlarr | find "RUNNING" >nul 2>&1
if errorlevel 1 (
    net start Prowlarr >nul 2>&1
)
timeout /t 2 /nobreak >nul

:: Backend — 先杀旧进程再启动
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
timeout /t 1 /nobreak >nul
start /b cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8001 >backend.log 2>&1"
timeout /t 3 /nobreak >nul

:: Frontend
start /b cmd /c "cd /d %~dp0frontend && npm run dev >frontend.log 2>&1"
timeout /t 5 /nobreak >nul

:: Open browser
start http://localhost:3032
