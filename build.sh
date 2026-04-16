#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build.sh — local convenience script to build the soundcraftuisc binary.
#
# Usage:
#   ./build.sh
#
# Output:
#   dist/soundcraftuisc        (Linux / macOS)
#   dist/soundcraftuisc.exe    (Windows / Git-Bash)
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v pyinstaller &>/dev/null; then
    echo "pyinstaller not found — installing dev extras..."
    pip install -e ".[dev]"
fi

echo "Building standalone binary..."
pyinstaller soundcraftuisc.spec

echo ""
echo "Done. Binary is at: dist/soundcraftuisc (or dist/soundcraftuisc.exe on Windows)"
