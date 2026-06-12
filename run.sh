#!/usr/bin/env bash
# Convenience launcher for the Swim Spa web app.
#
#   ./run.sh            -> connect to a real Gecko spa on your network
#   SPA_DEMO=1 ./run.sh -> run the built-in demo (no hardware required)
#
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
