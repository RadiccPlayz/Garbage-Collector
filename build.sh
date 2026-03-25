#!/usr/bin/env bash
# =============================================
# Build script — Garbage Collector (Linux)
# =============================================
set -e

EXE_NAME="GarbageCollector"
ENTRY="main.py"

echo "Cleaning previous builds..."
rm -rf build dist "${EXE_NAME}.spec"

echo "Building executable..."
pyinstaller --clean \
    --onefile \
    --noconsole \
    --name "$EXE_NAME" \
    --add-data "ui_styles.py:." \
    --add-data "ui_main.py:." \
    --add-data "workers.py:." \
    --add-data "cleanup_tasks.py:." \
    --add-data "platform_detect.py:." \
    "$ENTRY"

rm -rf build "${EXE_NAME}.spec"

echo ""
echo "Build complete. Executable: dist/${EXE_NAME}"
