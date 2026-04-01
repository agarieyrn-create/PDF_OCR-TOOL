# -*- mode: python ; coding: utf-8 -*-
"""
pdf_ocr_tool.spec
PyInstaller ビルド設定ファイル

生成物:
    dist/PDF_OCR_Tool/PDF_OCR_Tool.exe  (Windows)
    dist/PDF_OCR_Tool/PDF_OCR_Tool      (Mac)

使い方:
    cd build
    pyinstaller pdf_ocr_tool.spec --noconfirm
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

TOOL_DIR = Path("../tool").resolve()

# ---------------------------------------------------------------------------
# 各ライブラリの全ファイルを収集
# ---------------------------------------------------------------------------
fitz_d,     fitz_b,     fitz_h     = collect_all("fitz")
openpyxl_d, openpyxl_b, openpyxl_h = collect_all("openpyxl")
PIL_d,      PIL_b,      PIL_h       = collect_all("PIL")

block_cipher = None

a = Analysis(
    [str(TOOL_DIR / "gui.py")],
    pathex=[str(TOOL_DIR)],
    binaries=[] + fitz_b + openpyxl_b + PIL_b,
    datas=[] + fitz_d + openpyxl_d + PIL_d,
    hiddenimports=[
        "app_path",
        "main",
        "classifier",
        "pdf_reader",
        "ocr",
        "extractor",
        "extractor.base",
        "extractor.invoice",
        "extractor.delivery",
        "extractor.order",
        *fitz_h,
        *openpyxl_h,
        *PIL_h,
        "pytesseract",
        "pdf2image",
        "tkinter",
        "tkinter.ttk",
        "tkinter.scrolledtext",
        "tkinter.filedialog",
        "tkinter.messagebox",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "scipy", "pandas"],
    noarchive=False,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDF_OCR_Tool",
    debug=False,
    strip=False,
    upx=True,
    console=False,       # コンソールウィンドウを非表示（GUIアプリ）
    icon=None,           # アイコンを使う場合: icon="icon.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="PDF_OCR_Tool",
)
