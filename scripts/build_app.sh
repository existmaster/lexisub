#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Cleaning previous build…"
rm -rf build dist

echo "==> Running PyInstaller…"
uv run pyinstaller lexisub.spec --noconfirm --clean

echo "==> Done. Output:"
ls -la dist/

if [[ -d dist/Lexisub.app ]]; then
  echo
  echo "==> .app size:"
  du -sh dist/Lexisub.app
  echo
  echo "==> To run:"
  echo "    xattr -dr com.apple.quarantine dist/Lexisub.app"
  echo "    open dist/Lexisub.app"
fi
