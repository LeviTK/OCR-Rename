@echo off
setlocal
set "ORIGINAL_DIR=%cd%"
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ❌ 虚拟环境不存在，请先运行 setup.bat
    exit /b 1
)

if /I "%~1"=="-h" goto :help
if /I "%~1"=="--help" goto :help

if "%~1"=="" (
    set "BASE_DIR=%ORIGINAL_DIR%"
) else (
    pushd "%ORIGINAL_DIR%" >nul
    for %%I in ("%~1") do set "BASE_DIR=%%~fI"
    popd >nul
)

set "INPUT_DIR=%BASE_DIR%\000-Pic"
if not exist "%INPUT_DIR%" (
    echo ❌ 目录不存在: %INPUT_DIR%
    exit /b 1
)

.venv\Scripts\python.exe -m src scan --input "%INPUT_DIR%"
exit /b %errorlevel%

:help
echo 用法: run.bat [父目录路径]
echo 说明: 默认处理 [父目录]\000-Pic 下的图片，执行二维码识别并原地重命名
exit /b 0
