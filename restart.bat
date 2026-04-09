@echo off
:: 重启前后端（一键）
:: 如果传入参数 silent 则不打开浏览器
cd /d %~dp0

echo [1/3] Stopping...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/3] Starting Backend...
start /b cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 >backend.log 2>&1"
timeout /t 3 /nobreak >nul

echo [3/3] Starting Frontend...
start /b cmd /c "cd /d %~dp0frontend && npm run dev >frontend.log 2>&1"
timeout /t 5 /nobreak >nul

echo Done! http://localhost:3031
if /i not "%1"=="silent" start http://localhost:3031
