#!/usr/bin/env bash
# One-Click Cleanup for Code Knowledge Chain (macOS / Linux)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/scripts/cleanup.py" "$@"
