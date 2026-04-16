#!/bin/bash
set -euo pipefail

ORIG_PWD="$(pwd)"
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "❌ 虚拟环境不存在，请先运行 ./setup.sh"
    exit 1
fi

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    echo "用法: ./run.sh [图片目录]"
    echo "说明: 默认处理项目内的 001-Pic/，执行识别并原地重命名"
    exit 0
fi

if [ -z "${1:-}" ]; then
    INPUT_DIR="$(pwd)/001-Pic"
elif [[ "$1" = /* ]]; then
    INPUT_DIR="$1"
else
    INPUT_DIR="$ORIG_PWD/$1"
fi

if [ ! -d "$INPUT_DIR" ]; then
    echo "❌ 目录不存在: $INPUT_DIR"
    exit 1
fi

if [ "$(uname -s)" = "Darwin" ]; then
    DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m src --input "$INPUT_DIR"
else
    .venv/bin/python -m src --input "$INPUT_DIR"
fi
