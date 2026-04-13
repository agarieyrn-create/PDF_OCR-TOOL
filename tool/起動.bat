@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo PDF OCR ツールを起動します...

REM Python が使えるか確認
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python が見つかりません。Python 3.10以上をインストールしてください。
    pause
    exit /b 1
)

REM 依存ライブラリのインストール確認
python -c "import fitz, openpyxl" >nul 2>&1
if %errorlevel% neq 0 (
    echo 必要なライブラリをインストールしています...
    pip install -r requirements.txt
)

REM GUI 起動
python gui.py
