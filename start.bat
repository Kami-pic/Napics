@echo off
:: 只启动前后端（Alist/qB/Prowlarr 假设已在运行）
:: 如需全部启动请用 start_all.bat

cd /d %~dp0

echo ========================================
echo   Starting Frontend + Backend only
echo ========================================

:: Backend — 先杀旧进程再启动
echo [1/2] Starting Backend...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
timeout /t 1 /nobreak >nul
start /b cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 >backend.log 2>&1"
timeout /t 3 /nobreak >nul
echo     Backend started (port 8000)

:: Frontend
echo [2/2] Starting Frontend...
start /b cmd /c "cd /d %~dp0frontend && npm run dev >frontend.log 2>&1"
timeout /t 5 /nobreak >nul
echo     Frontend started (port 3031)

echo.
echo   Open http://localhost:3031
echo ========================================
start http://localhost:3031
