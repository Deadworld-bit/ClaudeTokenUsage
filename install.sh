#!/usr/bin/env bash
# Claude token-usage tracker installer (Linux / macOS / Git Bash on Windows).
set -eu

DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo "ERROR: Python 3 is required but was not found on PATH." >&2
  echo "Install Python 3 from https://www.python.org/downloads/ and re-run." >&2
  exit 1
fi

exec "$PY" "$DIR/install.py" "$@"
