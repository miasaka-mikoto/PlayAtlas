#!/usr/bin/env sh
# Headless rule-layer QA. This does not claim a Windows/Android or visual run.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "${PYTHON:-python3}" "$SCRIPT_DIR/tools/run_qa.py" --project-root "$SCRIPT_DIR" "$@"

