@echo off
:: 重启前后端（一键停止 + 启动）
:: 传入参数 silent 则不打开浏览器
:: 无窗口模式：双击时通过 VBS 隐藏自身重启

if not "%HIDDEN%"=="1" (
    set "HIDDEN=1"
    cscript //nologo "%~dp0_start_hidden.vbs" "%~f0" %*
    exit /b
)

cd /d %~dp0

echo [1/4] Stopping Backend...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1

echo [2/4] Stopping Frontend...
taskkill /f /im node.exe >nul 2>&1

echo [3/4] Waiting for port 8001 to be released...
set /a count=0
:wait_port
netstat -aon | findstr ":8001" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    set /a count+=1
    if %count% geq 15 (
        for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
        timeout /t 3 /nobreak >nul
    ) else (
        timeout /t 1 /nobreak >nul
        goto wait_port
    )
)

echo [4/4] Starting...
start /b cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8001 >backend.log 2>&1"
timeout /t 3 /nobreak >nul
start /b cmd /c "cd /d %~dp0frontend && npm run dev >frontend.log 2>&1"
timeout /t 5 /nobreak >nul

if /i not "%1"=="silent" start http://localhost:3032
