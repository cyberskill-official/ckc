#!/usr/bin/env bash
# One-Click Cleanup for Code Knowledge Chain (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Initialize pyenv if available to pick up user's configured Python
if command -v pyenv >/dev/null 2>&1; then
    eval "$(pyenv init -)" 2>/dev/null || true
fi

# Find a Python 3.10+ interpreter
PYTHON_BIN=""
for candidate in python3 python python3.14 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ] && [ -x "$HOME/.pyenv/shims/python3" ]; then
    PYTHON_BIN="$HOME/.pyenv/shims/python3"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "Error: Python 3.10+ is required, but no compatible interpreter was found." >&2
    exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/scripts/cleanup.py" "$@"
