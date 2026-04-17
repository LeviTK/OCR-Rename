@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "INPUT_DIR=%cd%\input"

if not exist "%INPUT_DIR%" mkdir "%INPUT_DIR%"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] First run detected, bootstrapping local environment...
    call "%~dp0setup.bat"
    if errorlevel 1 (
        echo.
        echo [ERROR] Environment setup failed.
        echo [INFO] See SCRIPT_GUIDE.txt for start/setup/run differences.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo [2/3] Processing folder: "%INPUT_DIR%"
.venv\Scripts\python.exe -m src scan "%INPUT_DIR%"
set "EXIT_CODE=%errorlevel%"

echo.
if "%EXIT_CODE%"=="0" (
    echo [3/3] Done. Check the input folder for renamed files.
) else (
    echo [3/3] Failed with exit code: %EXIT_CODE%
)
echo.
pause
exit /b %EXIT_CODE%
