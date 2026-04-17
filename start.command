#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

INPUT_DIR="$(pwd)/input"
mkdir -p "$INPUT_DIR"

if [ ! -x ".venv/bin/python" ]; then
    echo "[1/3] First run detected, bootstrapping local environment..."
    bash ./setup.sh || {
        echo
        echo "[ERROR] Environment setup failed."
        echo
        read -r -n 1 -s -p "Press any key to close..."
        echo
        exit 1
    }
fi

echo
echo "[2/3] Processing folder: $INPUT_DIR"
set +e
./.venv/bin/python -m src scan "$INPUT_DIR"
status=$?
set -e

echo
if [ "$status" -eq 0 ]; then
    echo "[3/3] Done. Check the input folder for renamed files."
else
    echo "[3/3] Failed with exit code: $status"
fi
echo
read -r -n 1 -s -p "Press any key to close..."
echo
exit "$status"
