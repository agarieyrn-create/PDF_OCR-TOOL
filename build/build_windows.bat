@echo off
chcp 65001 >nul
setlocal

echo ============================================
echo  PDF OCR Tool  Windows ビルドスクリプト
echo ============================================
echo.

REM ── ① 作業ディレクトリをこのファイルの場所に固定 ──
cd /d "%~dp0"

REM ── ② PyInstaller インストール ──
echo [1/5] PyInstaller を確認しています...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller をインストールしています...
    pip install pyinstaller
)

REM ── ③ 古いビルドを削除 ──
echo [2/5] 以前のビルドを削除しています...
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__

REM ── ④ ビルド実行 ──
echo [3/5] ビルドを実行しています（数分かかります）...
pyinstaller pdf_ocr_tool.spec --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] ビルドに失敗しました。
    pause
    exit /b 1
)

REM ── ⑤ データファイルをコピー ──
echo [4/5] 設定ファイルをコピーしています...

set DEST=dist\PDF_OCR_Tool

REM rules フォルダ
xcopy /E /I /Y ..\tool\rules "%DEST%\rules" >nul

REM config.json
copy /Y ..\tool\config.json "%DEST%\config.json" >nul

REM 空フォルダ（.gitkeep で存在を示す）
if not exist "%DEST%\input"  mkdir "%DEST%\input"
if not exist "%DEST%\output" mkdir "%DEST%\output"
if not exist "%DEST%\logs"   mkdir "%DEST%\logs"

echo PDFをここに入れてください。 > "%DEST%\input\ここにPDFを入れてください.txt"

REM ── ⑥ ZIP 圧縮 ──
echo [5/5] ZIP ファイルを作成しています...
if exist "PDF_OCR_Tool_Windows.zip" del "PDF_OCR_Tool_Windows.zip"
powershell -Command "Compress-Archive -Path 'dist\PDF_OCR_Tool' -DestinationPath 'PDF_OCR_Tool_Windows.zip'"

echo.
echo ============================================
echo  ビルド完了！
echo ============================================
echo.
echo  配布ファイル: build\PDF_OCR_Tool_Windows.zip
echo  内容確認:     build\dist\PDF_OCR_Tool\
echo.
echo  ユーザーへの配布手順:
echo    1. PDF_OCR_Tool_Windows.zip を渡す
echo    2. 解凍して PDF_OCR_Tool.exe をダブルクリック
echo.
pause
