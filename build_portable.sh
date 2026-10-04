#!/usr/bin/env sh
# Build a source-first portable archive. No native executable is fabricated.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "${PYTHON:-python3}" "$SCRIPT_DIR/tools/build_portable.py" --project-root "$SCRIPT_DIR" "$@"

