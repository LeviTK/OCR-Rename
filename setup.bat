@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_BIN="
where py >nul 2>nul
if not errorlevel 1 (
    if exist "wheels\" (
        py -3.10 --version >nul 2>nul
        if not errorlevel 1 set "PYTHON_BIN=py -3.10"
    ) else (
        py -3 --version >nul 2>nul
        if not errorlevel 1 set "PYTHON_BIN=py -3"
    )
)
if not defined PYTHON_BIN (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_BIN=python"
)
if not defined PYTHON_BIN (
    echo [ERROR] Python was not found. Install Python 3.10 and add it to PATH.
    exit /b 1
)

echo [1/4] Checking Python...
%PYTHON_BIN% --version

for /f %%i in ('%PYTHON_BIN% -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))"') do set "PYTHON_MM=%%i"
for /f %%i in ('%PYTHON_BIN% -c "import struct; print(struct.calcsize(''P'') * 8)"') do set "PYTHON_BITS=%%i"

if not defined PYTHON_MM (
    echo [ERROR] Failed to detect Python major/minor version.
    exit /b 1
)
if not defined PYTHON_BITS (
    echo [ERROR] Failed to detect Python bitness.
    exit /b 1
)

echo [2/4] Creating local virtual environment...
%PYTHON_BIN% -m venv .venv
if errorlevel 1 exit /b 1

if not exist "input" mkdir "input"

echo [3/4] Installing Python dependencies...
if exist "wheels\" (
    if not "%PYTHON_MM%"=="3.10" (
        echo [ERROR] Offline wheels require Python 3.10. Found %PYTHON_MM%.
        exit /b 1
    )
    if not "%PYTHON_BITS%"=="64" (
        echo [ERROR] Offline wheels require 64-bit Python. Found %PYTHON_BITS%-bit.
        exit /b 1
    )
    echo [INFO] Using bundled offline wheels...
    .venv\Scripts\python.exe -m pip install --no-index --find-links wheels setuptools wheel packaging
    if errorlevel 1 exit /b 1
    .venv\Scripts\python.exe -m pip install --no-index --find-links wheels .
    if errorlevel 1 exit /b 1
) else (
    .venv\Scripts\python.exe -m pip install --upgrade pip
    if errorlevel 1 exit /b 1
    .venv\Scripts\python.exe -m pip install -e .
    if errorlevel 1 exit /b 1
)

echo [4/4] Verifying install...
.venv\Scripts\python.exe -c "from src.config import setup_platform; setup_platform(); import PIL, cv2, numpy, zxingcpp; from pyzbar.pyzbar import decode; print('Dependency check passed')"
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m src --help >nul
if errorlevel 1 exit /b 1
echo CLI check passed: ocr-rename

echo.
where tesseract >nul 2>nul
if errorlevel 1 (
    echo [WARN] Tesseract was not found in PATH.
    echo [WARN] QR and barcode scanning still work, but OCR fallback will be limited.
    echo [INFO] Download: https://github.com/UB-Mannheim/tesseract/wiki
) else (
    for /f "delims=" %%i in ('tesseract --version 2^>nul ^| findstr /R "^tesseract"') do (
        echo %%i
        goto :after_tesseract
    )
)
:after_tesseract

echo.
echo [OK] Setup complete.
echo [INFO] Put images into: input\
echo [INFO] Double-click: start.bat
echo [INFO] Manual run : .venv\Scripts\python.exe -m src scan "D:\images"
echo [INFO] Script guide: SCRIPT_GUIDE.txt
exit /b 0
