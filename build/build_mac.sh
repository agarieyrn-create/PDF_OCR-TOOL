#!/bin/bash
# ==================================================
#  PDF OCR Tool  Mac ビルドスクリプト
# ==================================================
set -e

cd "$(dirname "$0")"

echo "============================================"
echo " PDF OCR Tool  Mac ビルドスクリプト"
echo "============================================"
echo ""

# ── ① PyInstaller 確認 ──
echo "[1/5] PyInstaller を確認しています..."
if ! pip3 show pyinstaller &>/dev/null; then
    echo "PyInstaller をインストールしています..."
    pip3 install pyinstaller
fi

# ── ② 古いビルドを削除 ──
echo "[2/5] 以前のビルドを削除しています..."
rm -rf dist __pycache__

# ── ③ ビルド実行 ──
echo "[3/5] ビルドを実行しています（数分かかります）..."
pyinstaller pdf_ocr_tool.spec --noconfirm

# ── ④ データファイルをコピー ──
echo "[4/5] 設定ファイルをコピーしています..."

DEST="dist/PDF_OCR_Tool"

cp -r ../tool/rules  "$DEST/rules"
cp    ../tool/config.json "$DEST/config.json"

mkdir -p "$DEST/input"
mkdir -p "$DEST/output"
mkdir -p "$DEST/logs"

echo "PDFをここに入れてください。" > "$DEST/input/ここにPDFを入れてください.txt"

# ── ⑤ ZIP 圧縮 ──
echo "[5/5] ZIP ファイルを作成しています..."
rm -f PDF_OCR_Tool_Mac.zip
cd dist
zip -r ../PDF_OCR_Tool_Mac.zip PDF_OCR_Tool
cd ..

echo ""
echo "============================================"
echo " ビルド完了！"
echo "============================================"
echo ""
echo " 配布ファイル: build/PDF_OCR_Tool_Mac.zip"
echo " 内容確認:     build/dist/PDF_OCR_Tool/"
echo ""
echo " ユーザーへの配布手順:"
echo "   1. PDF_OCR_Tool_Mac.zip を渡す"
echo "   2. 解凍して PDF_OCR_Tool をダブルクリック"
echo ""
