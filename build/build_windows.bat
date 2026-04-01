@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo ============================================
echo  PDF OCR Tool - Windows Build Script
echo ============================================
echo.

REM ----- Step 1: Check PyInstaller -----
echo [Step 1/5] Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo ERROR: pip install failed. Please run: pip install pyinstaller
        pause
        exit /b 1
    )
)
echo   OK

REM ----- Step 2: Clean previous build -----
echo [Step 2/5] Cleaning previous build...
if exist dist rmdir /s /q dist
echo   OK

REM ----- Step 3: Run PyInstaller -----
echo [Step 3/5] Building exe (this may take a few minutes)...
pyinstaller pdf_ocr_tool.spec --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed. Check the output above for details.
    pause
    exit /b 1
)
echo   OK

REM ----- Step 4: Copy config and data files -----
echo [Step 4/5] Copying config and rules...

set DEST=dist\PDF_OCR_Tool

if not exist "%DEST%\rules" mkdir "%DEST%\rules"
xcopy /E /I /Y ..\tool\rules "%DEST%\rules" >nul
copy /Y ..\tool\config.json "%DEST%\config.json" >nul

if not exist "%DEST%\input"  mkdir "%DEST%\input"
if not exist "%DEST%\output" mkdir "%DEST%\output"
if not exist "%DEST%\logs"   mkdir "%DEST%\logs"

echo Put your PDF files here. > "%DEST%\input\README.txt"
echo   OK

REM ----- Step 5: Create ZIP -----
echo [Step 5/5] Creating ZIP...
if exist "PDF_OCR_Tool_Windows.zip" del "PDF_OCR_Tool_Windows.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\PDF_OCR_Tool' -DestinationPath 'PDF_OCR_Tool_Windows.zip'"
if %errorlevel% neq 0 (
    echo WARNING: ZIP creation failed. Use the folder directly: dist\PDF_OCR_Tool\
) else (
    echo   OK
)

echo.
echo ============================================
echo  Build Complete!
echo ============================================
echo.
echo  For distribution : build\PDF_OCR_Tool_Windows.zip
echo  Test run folder  : build\dist\PDF_OCR_Tool\PDF_OCR_Tool.exe
echo.
echo  Send the ZIP to users. They just unzip and double-click PDF_OCR_Tool.exe
echo.
pause
