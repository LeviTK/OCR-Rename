@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

where py >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python launcher was not found. Install Python 3.10 x64 first.
    exit /b 1
)

py -3.10 Release\build_windows_exe.py
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" exit /b %EXIT_CODE%

echo.
echo [OK] Windows EXE package created.
pause
exit /b 0
