@echo off
:: 重启前后端（一键）
:: 如果传入参数 silent 则不打开浏览器
cd /d %~dp0

echo [1/4] Stopping Backend...
:: 杀掉所有占用 8000 端口的进程
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
:: 兜底：杀掉所有 uvicorn 相关的 python 进程
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%uvicorn%%'" get processid /value 2^>nul ^| findstr "="') do (
    set "pid=%%a"
    setlocal enabledelayedexpansion
    set "pid=!pid:ProcessId=!"
    set "pid=!pid:~1!"
    if not "!pid!"=="" taskkill /f /pid !pid! >nul 2>&1
    endlocal
)

echo [2/4] Stopping Frontend...
taskkill /f /im node.exe >nul 2>&1

echo [3/4] Waiting for port 8000 to be released...
:: 循环等待端口释放，最多等 15 秒
set /a count=0
:wait_port
netstat -aon | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    set /a count+=1
    if %count% geq 15 (
        echo WARNING: Port 8000 still occupied after 15s, force killing all python...
        taskkill /f /im python.exe >nul 2>&1
        timeout /t 3 /nobreak >nul
    ) else (
        timeout /t 1 /nobreak >nul
        goto wait_port
    )
)
echo Port 8000 is free.

echo [4/4] Starting...
start /b cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 >backend.log 2>&1"
timeout /t 3 /nobreak >nul
start /b cmd /c "cd /d %~dp0frontend && npm run dev >frontend.log 2>&1"
timeout /t 5 /nobreak >nul

echo Done! http://localhost:3031
if /i not "%1"=="silent" start http://localhost:3031
