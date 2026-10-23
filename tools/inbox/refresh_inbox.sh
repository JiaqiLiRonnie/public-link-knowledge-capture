#!/bin/sh
# Rebuild the inbox outputs. Set PYTHON to choose a Python interpreter.
set -eu
SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PYTHON=${PYTHON:-python3}
"$PYTHON" "$SCRIPT_DIR/build_inbox.py"
