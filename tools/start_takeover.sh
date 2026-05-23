#!/usr/bin/env bash
set -euo pipefail

DEVICE_ID="${1:-cf2a0e6e}"
PORT="${2:-8765}"
HOST="${3:-0.0.0.0}"
ADB_BIN_DEFAULT="/home/qiao/vscode/.tmp/scrcpy-3.3.4/scrcpy-linux-x86_64-v3.3.4/adb"

if [[ -x "$ADB_BIN_DEFAULT" ]]; then
  export ADB_BIN="$ADB_BIN_DEFAULT"
fi

cd /home/qiao/vscode/Open-AutoGLM
. .venv/bin/activate
python tools/web_takeover.py --device-id "$DEVICE_ID" --host "$HOST" --port "$PORT"
