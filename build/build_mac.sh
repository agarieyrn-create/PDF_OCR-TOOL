#!/bin/bash
# ==================================================
#  PDF OCR Tool - Mac Build Script
# ==================================================
set -e
cd "$(dirname "$0")"

echo "============================================"
echo " PDF OCR Tool - Mac Build Script"
echo "============================================"
echo ""

# ----- Step 1: Check PyInstaller -----
echo "[Step 1/5] Checking PyInstaller..."
if ! pip3 show pyinstaller &>/dev/null; then
    echo "  Installing PyInstaller..."
    pip3 install pyinstaller
fi
echo "  OK"

# ----- Step 2: Clean previous build -----
echo "[Step 2/5] Cleaning previous build..."
rm -rf dist __pycache__
echo "  OK"

# ----- Step 3: Run PyInstaller -----
echo "[Step 3/5] Building app (this may take a few minutes)..."
pyinstaller pdf_ocr_tool.spec --noconfirm
echo "  OK"

# ----- Step 4: Copy config and data files -----
echo "[Step 4/5] Copying config and rules..."

DEST="dist/PDF_OCR_Tool"

cp -r ../tool/rules  "$DEST/rules"
cp    ../tool/config.json "$DEST/config.json"

mkdir -p "$DEST/input"
mkdir -p "$DEST/output"
mkdir -p "$DEST/logs"

echo "Put your PDF files here." > "$DEST/input/README.txt"
echo "  OK"

# ----- Step 5: Create ZIP -----
echo "[Step 5/5] Creating ZIP..."
rm -f PDF_OCR_Tool_Mac.zip
cd dist && zip -r ../PDF_OCR_Tool_Mac.zip PDF_OCR_Tool && cd ..
echo "  OK"

echo ""
echo "============================================"
echo " Build Complete!"
echo "============================================"
echo ""
echo " For distribution : build/PDF_OCR_Tool_Mac.zip"
echo " Test run folder  : build/dist/PDF_OCR_Tool/PDF_OCR_Tool"
echo ""
echo " Send the ZIP to users. They just unzip and double-click PDF_OCR_Tool"
echo ""
