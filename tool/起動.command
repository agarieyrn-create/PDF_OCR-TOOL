#!/bin/bash
# Mac用 ダブルクリック起動スクリプト
# 初回: chmod +x 起動.command

cd "$(dirname "$0")"

echo "PDF OCR ツールを起動します..."

# Python3 確認
if ! command -v python3 &>/dev/null; then
    osascript -e 'display dialog "Python3 が見つかりません。\nhttps://www.python.org/ からインストールしてください。" buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# 依存ライブラリ確認
python3 -c "import fitz, openpyxl" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "必要なライブラリをインストールしています..."
    pip3 install -r requirements.txt
fi

python3 gui.py
