@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_BIN="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_BIN=py -3"
if not defined PYTHON_BIN (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_BIN=python"
)
if not defined PYTHON_BIN (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.10+ 并加入 PATH
    exit /b 1
)

echo [1/4] Python 检测...
%PYTHON_BIN% --version

echo [2/4] 创建虚拟环境...
%PYTHON_BIN% -m venv .venv
if errorlevel 1 exit /b 1

echo [3/4] 安装 Python 依赖...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo [4/4] 依赖自检...
.venv\Scripts\python.exe -c "import PIL, cv2, numpy, pyzbar, zxingcpp; print('Python 依赖检查通过')"
if errorlevel 1 exit /b 1

echo.
where tesseract >nul 2>nul
if errorlevel 1 (
    echo [WARN] 未检测到 Tesseract，请安装并加入 PATH:
    echo        https://github.com/UB-Mannheim/tesseract/wiki
) else (
    for /f "delims=" %%i in ('tesseract --version 2^>nul ^| findstr /R "^tesseract"') do (
        echo %%i
        goto :tess_done
    )
)
:tess_done

echo.
echo ✅ 安装完成
echo    运行: run.bat                  (默认处理项目内的 001-Pic)
echo    或者: run.bat "D:\images"
endlocal
