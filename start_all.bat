@echo off
:: 检测是否已在隐藏模式运行，如果不是则通过 VBS 隐藏重启
if not "%HIDDEN%"=="1" (
    set "HIDDEN=1"
    cscript //nologo "%~dp0_start_hidden.vbs" "%~f0"
    exit /b
)

cd /d %~dp0

:: Alist（修改为你的 Alist 安装路径）
start /b cmd /c "cd /d %~dp0..\Alist && alist.exe server >nul 2>&1"
timeout /t 2 /nobreak >nul

:: qBittorrent
tasklist /fi "imagename eq qbittorrent.exe" | find /i "qbittorrent.exe" >nul 2>&1
if errorlevel 1 (
    start "" "C:\Program Files\qBittorrent\qbittorrent.exe" --no-splash
)
timeout /t 2 /nobreak >nul

:: Prowlarr
sc query Prowlarr | find "RUNNING" >nul 2>&1
if errorlevel 1 (
    net start Prowlarr >nul 2>&1
)
timeout /t 2 /nobreak >nul

:: Backend — 先杀旧进程再启动
taskkill /f /im python.exe >nul 2>&1
timeout /t 1 /nobreak >nul
start /b cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload >nul 2>&1"
timeout /t 3 /nobreak >nul

:: Frontend
start /b cmd /c "cd /d %~dp0frontend && npm run dev >nul 2>&1"
timeout /t 5 /nobreak >nul

:: Open browser
start http://localhost:3031
