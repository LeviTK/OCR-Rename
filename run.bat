@echo off
setlocal EnableExtensions
set "ORIGINAL_DIR=%cd%"
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv was not found. Run setup.bat first.
    exit /b 1
)

if /I "%~1"=="-h" goto :help
if /I "%~1"=="--help" goto :help

if "%~1"=="" (
    set "INPUT_DIR=%cd%\input"
) else (
    pushd "%ORIGINAL_DIR%" >nul
    for %%I in ("%~1") do set "INPUT_DIR=%%~fI"
    popd >nul
)

if not exist "%INPUT_DIR%" (
    echo [ERROR] Folder not found: %INPUT_DIR%
    exit /b 1
)

.venv\Scripts\python.exe -m src scan "%INPUT_DIR%"
exit /b %errorlevel%

:help
echo Usage: run.bat [image_folder]
echo Info : Default folder is .\input
echo Info : Run setup.bat first if .venv does not exist.
exit /b 0
