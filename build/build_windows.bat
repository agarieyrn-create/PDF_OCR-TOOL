@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo ============================================
echo  PDF OCR Tool - Windows Build Script
echo ============================================
echo.

REM ----- Path length check (Windows MAX_PATH = 260) -----
set CURRENT_DIR=%~dp0
set DIR_LEN=0
:count_len
if "!CURRENT_DIR:~%DIR_LEN%,1!" == "" goto count_done
set /a DIR_LEN+=1
goto count_len
:count_done

if %DIR_LEN% GTR 80 (
    echo ============================================
    echo  WARNING: Current path is too long!
    echo ============================================
    echo.
    echo  Current path (%DIR_LEN% chars): %CURRENT_DIR%
    echo.
    echo  PyInstaller creates deeply nested output files.
    echo  If the total path exceeds 260 chars, Windows will
    echo  fail with error 0x80010135 (path too long).
    echo.
    echo  RECOMMENDED: Move this folder to a short path, e.g.:
    echo    C:\PDF_OCR_Build\
    echo.
    echo  Press any key to continue anyway, or Ctrl+C to cancel.
    pause >nul
    echo.
)

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
    echo.
    echo  Common causes:
    echo    - Path too long: Move folder to C:\PDF_OCR_Build\ and retry
    echo    - Missing library: pip install PyMuPDF openpyxl Pillow pdf2image pytesseract
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

REM Wait for antivirus / indexer to release file handles
echo   Waiting 5 seconds for file handles to be released...
timeout /t 5 /nobreak >nul

REM Try tar first (built-in on Windows 10 build 17063+)
where tar >nul 2>&1
if %errorlevel% equ 0 (
    echo   Using tar...
    tar -a -c -f PDF_OCR_Tool_Windows.zip -C dist PDF_OCR_Tool
    if %errorlevel% equ 0 (
        echo   OK
        goto :build_done
    )
    echo   tar failed, trying PowerShell...
)

REM Fallback: PowerShell Compress-Archive with -Force
echo   Using PowerShell...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Compress-Archive -Path 'dist\PDF_OCR_Tool' -DestinationPath 'PDF_OCR_Tool_Windows.zip' -Force; Write-Host '  ZIP OK' } catch { Write-Host ('  ZIP failed: ' + $_.Exception.Message) }"

if exist "PDF_OCR_Tool_Windows.zip" (
    echo   OK
    goto :build_done
)

REM Both failed - instruct manual zip
echo.
echo   NOTE: Automatic ZIP failed (antivirus may still be scanning files).
echo   The distribution folder is ready. Please zip it manually:
echo     1. Open Explorer and go to: %~dp0dist\
echo     2. Right-click "PDF_OCR_Tool" folder
echo     3. Choose "Send to" - "Compressed (zipped) folder"

:build_done
echo.
echo ============================================
echo  Build Complete!
echo ============================================
echo.
if exist "PDF_OCR_Tool_Windows.zip" (
    echo  Distribution ZIP : %~dp0PDF_OCR_Tool_Windows.zip
) else (
    echo  Distribution folder : %~dp0dist\PDF_OCR_Tool\  ^(zip manually^)
)
echo  Test the exe at  : %~dp0dist\PDF_OCR_Tool\PDF_OCR_Tool.exe
echo.
echo  How to ship to users:
echo    1. Send PDF_OCR_Tool_Windows.zip
echo    2. Users unzip it - no installation needed
echo    3. Double-click PDF_OCR_Tool.exe to launch
echo.
pause
