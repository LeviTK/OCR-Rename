#!/bin/bash
set -uo pipefail
cd "$(dirname "$0")"
./run.sh "$@"
status=$?
echo
read -r -n 1 -s -p "Press any key to close..."
echo
exit "$status"
