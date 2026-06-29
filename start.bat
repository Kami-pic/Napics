@echo off
:: 只启动前后端（Alist/qB/Prowlarr 假设已在运行）
:: 如需全部启动请用 start_all.bat
:: 无窗口模式：双击时通过 VBS 隐藏自身重启

if not "%HIDDEN%"=="1" (
    set "HIDDEN=1"
    cscript //nologo "%~dp0_start_hidden.vbs" "%~f0"
    exit /b
)

cd /d %~dp0

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
