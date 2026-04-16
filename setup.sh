#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/4] 检测 Python3..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    echo "❌ 未检测到 python3，请先安装 Python 3.10+"
    exit 1
fi
"$PYTHON_BIN" --version

echo "[2/4] 检测并安装系统依赖..."
if [ "$(uname -s)" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
        brew list zbar >/dev/null 2>&1 || brew install zbar
        brew list tesseract >/dev/null 2>&1 || brew install tesseract
    else
        echo "⚠️ 未检测到 Homebrew，请手动安装 zbar 和 tesseract"
    fi
else
    echo "⚠️ 当前非 macOS，跳过系统依赖自动安装"
fi

echo "[3/4] 创建虚拟环境并安装 Python 依赖..."
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .

echo "[4/4] 依赖自检..."
.venv/bin/python -c "import PIL, cv2, numpy, pyzbar, zxingcpp; print('Python 依赖检查通过')"
.venv/bin/ocr-rename --help >/dev/null
echo "CLI 安装通过: ocr-rename"

if command -v tesseract >/dev/null 2>&1; then
    tesseract --version | head -n 1
else
    echo "⚠️ 未检测到 tesseract，可继续运行但 OCR 兜底能力受限"
fi

echo ""
echo "✅ 安装完成"
echo "   运行: .venv/bin/ocr-rename scan /path/to/images"
echo "   或者: ./run.sh /path/to/images"
