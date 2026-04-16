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
    set "INPUT_DIR=%cd%\001-Pic"
) else (
    pushd "%ORIGINAL_DIR%" >nul
    for %%I in ("%~1") do set "INPUT_DIR=%%~fI"
    popd >nul
)

if not exist "%INPUT_DIR%" (
    echo ❌ 目录不存在: %INPUT_DIR%
    exit /b 1
)

.venv\Scripts\python.exe -m src --input "%INPUT_DIR%"
exit /b %errorlevel%

:help
echo 用法: run.bat [图片目录]
echo 说明: 默认处理项目内的 001-Pic\，执行识别并原地重命名
exit /b 0
