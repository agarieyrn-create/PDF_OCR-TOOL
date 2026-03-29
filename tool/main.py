"""
main.py
PDF OCRツールのエントリーポイント。

処理フロー:
    1. inputフォルダのPDFを順次処理
    2. pdfplumberでテキスト抽出（失敗時はpytesseractでOCR）
    3. キーワードスコアリングでドキュメント分類
    4. 種別に応じたエクストラクタでヘッダ・明細を抽出
    5. output/result.xlsx に出力
    6. logs/ にログ記録
"""
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from pdf_reader import extract_text_from_pdf
from ocr import ocr_pdf
from classifier import classify_document
from extractor.invoice import InvoiceExtractor
from extractor.delivery import DeliveryExtractor
from extractor.order import OrderExtractor

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

HEADER_COLUMNS = ["ファイル名", "種類", "日付", "金額", "会社名", "番号"]
DETAIL_COLUMNS = ["ファイル名", "行番号", "品名", "数量", "単価", "金額"]

DOC_TYPE_LABELS = {
    "invoice":  "請求書",
    "delivery": "納品書",
    "order":    "発注書",
    "unknown":  "不明",
}

EXTRACTOR_MAP = {
    "invoice":  InvoiceExtractor,
    "delivery": DeliveryExtractor,
    "order":    OrderExtractor,
}

# Excelヘッダ行の背景色
HEADER_BG_COLOR = "2F5496"
HEADER_FONT_COLOR = "FFFFFF"


# ---------------------------------------------------------------------------
# セットアップ
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def setup_logging(log_dir: str) -> tuple[str, str]:
    """
    ファイルとコンソールへのログ設定。

    Returns:
        (log_file_path, error_file_path)
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file   = os.path.join(log_dir, "log.txt")
    error_file = os.path.join(log_dir, "error_files.txt")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file, error_file


# ---------------------------------------------------------------------------
# エクストラクタ取得
# ---------------------------------------------------------------------------

def get_extractor(doc_type: str, rules_dir: str):
    """ドキュメント種別に対応するエクストラクタインスタンスを返す。"""
    cls = EXTRACTOR_MAP.get(doc_type)
    if cls is None:
        return None
    rules_file = os.path.join(rules_dir, f"{doc_type}.json")
    if not os.path.exists(rules_file):
        logging.getLogger(__name__).error(f"ルールファイルが見つかりません: {rules_file}")
        return None
    return cls(rules_file)


# ---------------------------------------------------------------------------
# Excel出力
# ---------------------------------------------------------------------------

def _make_header_style(cell, bg: str = HEADER_BG_COLOR, fg: str = HEADER_FONT_COLOR):
    """Excelヘッダセルにスタイルを適用する。"""
    cell.font      = Font(bold=True, color=fg, name="Yu Gothic UI")
    cell.fill      = PatternFill(start_color=bg, end_color=bg, fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center")


def _auto_fit_columns(ws, min_width: int = 10, max_width: int = 50):
    """全列の幅をコンテンツに合わせて自動調整する。"""
    for col_cells in ws.columns:
        col_letter = get_column_letter(col_cells[0].column)
        max_len = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in col_cells
        )
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, min_width), max_width)


def write_excel(
    headers: list[list],
    details: list[list],
    output_path: str,
) -> None:
    """
    ヘッダ一覧・明細一覧を2シートのExcelファイルに出力する。

    Args:
        headers:     [[ファイル名, 種類, 日付, 金額, 会社名, 番号], ...]
        details:     [[ファイル名, 行番号, 品名, 数量, 単価, 金額], ...]
        output_path: 出力先ファイルパス
    """
    wb = openpyxl.Workbook()

    # --- シート1: ヘッダ ---
    ws1 = wb.active
    ws1.title = "ヘッダ"
    ws1.freeze_panes = "A2"

    for col, title in enumerate(HEADER_COLUMNS, 1):
        cell = ws1.cell(row=1, column=col, value=title)
        _make_header_style(cell)

    for row_data in headers:
        ws1.append(row_data)

    _auto_fit_columns(ws1)

    # --- シート2: 明細 ---
    ws2 = wb.create_sheet("明細")
    ws2.freeze_panes = "A2"

    for col, title in enumerate(DETAIL_COLUMNS, 1):
        cell = ws2.cell(row=1, column=col, value=title)
        _make_header_style(cell)

    for row_data in details:
        ws2.append(row_data)

    # 数値列に数値書式を設定（数量・単価・金額）
    num_cols = [4, 5, 6]  # 数量, 単価, 金額 (1-indexed)
    for row in ws2.iter_rows(min_row=2, max_row=ws2.max_row):
        for col_idx in num_cols:
            cell = row[col_idx - 1]
            if isinstance(cell.value, (int, float)):
                cell.number_format = '#,##0'

    _auto_fit_columns(ws2)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb.save(output_path)


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def process_pdf(
    pdf_path: Path,
    rules_dir: str,
    ocr_language: str,
    ocr_dpi: int,
    logger: logging.Logger,
) -> tuple[list, list]:
    """
    1つのPDFファイルを処理してヘッダ行・明細行を返す。

    Returns:
        (header_row, detail_rows)
        エラー時は (None, []) を返す。
    """
    filename = pdf_path.name

    # --- テキスト抽出 ---
    text = extract_text_from_pdf(str(pdf_path))
    if not text.strip():
        logger.info(f"テキスト抽出失敗、OCRにフォールバック: {filename}")
        text = ocr_pdf(str(pdf_path), language=ocr_language, dpi=ocr_dpi)

    if not text.strip():
        logger.error(f"テキスト抽出・OCR両方失敗: {filename}")
        return None, []

    # --- 分類 ---
    doc_type = classify_document(text, rules_dir)
    label    = DOC_TYPE_LABELS.get(doc_type, doc_type)
    logger.info(f"分類結果: {filename} -> {label} ({doc_type})")

    # --- エクストラクタ取得 ---
    extractor = get_extractor(doc_type, rules_dir)
    if extractor is None:
        header_row = [filename, label, None, None, None, None]
        return header_row, []

    # --- ヘッダ抽出 ---
    header  = extractor.extract_header(text)
    details = extractor.extract_details(text)

    header_row = [
        filename,
        label,
        header.get("date"),
        header.get("amount"),
        header.get("company"),
        header.get("number"),
    ]

    detail_rows = [
        [
            filename,
            i + 1,
            d.get("name"),
            d.get("quantity"),
            d.get("unit_price"),
            d.get("amount"),
        ]
        for i, d in enumerate(details)
    ]

    logger.info(f"完了: {filename} | 明細{len(detail_rows)}行")
    return header_row, detail_rows


def main() -> None:
    # --- 設定読み込み ---
    base_dir    = Path(__file__).parent
    config_path = base_dir / "config.json"
    config      = load_config(str(config_path))

    input_dir  = base_dir / config["input_dir"]
    output_dir = base_dir / config["output_dir"]
    log_dir    = base_dir / config["log_dir"]
    rules_dir  = base_dir / config["rules_dir"]

    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    _, error_file = setup_logging(str(log_dir))
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("PDF OCR Tool 開始")
    logger.info(f"入力フォルダ: {input_dir}")
    logger.info("=" * 60)

    # --- PDFファイル一覧取得 ---
    pdf_files = sorted(input_dir.glob("*.pdf")) + sorted(input_dir.glob("*.PDF"))
    # 重複除去（大文字小文字）
    seen = set()
    unique_pdfs = []
    for p in pdf_files:
        if p.name.lower() not in seen:
            seen.add(p.name.lower())
            unique_pdfs.append(p)
    pdf_files = unique_pdfs

    if not pdf_files:
        logger.warning(f"inputフォルダにPDFが見つかりません: {input_dir}")
        logger.info("PDFファイルをinputフォルダに配置して再実行してください。")
        return

    logger.info(f"{len(pdf_files)}件のPDFを処理します")

    # --- 各PDFを処理 ---
    all_headers: list[list] = []
    all_details: list[list] = []
    error_files: list[str]  = []

    ocr_language = config.get("ocr_language", "jpn+eng")
    ocr_dpi      = config.get("ocr_dpi", 300)

    for pdf_path in pdf_files:
        logger.info(f"処理中 ({pdf_files.index(pdf_path) + 1}/{len(pdf_files)}): {pdf_path.name}")
        try:
            header_row, detail_rows = process_pdf(
                pdf_path, str(rules_dir), ocr_language, ocr_dpi, logger
            )
            if header_row is None:
                error_files.append(pdf_path.name)
            else:
                all_headers.append(header_row)
                all_details.extend(detail_rows)

        except Exception as e:
            logger.error(f"予期しないエラー ({pdf_path.name}): {e}", exc_info=True)
            error_files.append(pdf_path.name)

    # --- Excel出力 ---
    output_path = output_dir / config.get("output_file", "result.xlsx")
    try:
        write_excel(all_headers, all_details, str(output_path))
        logger.info(f"Excel出力完了: {output_path}")
    except Exception as e:
        logger.error(f"Excel出力失敗: {e}", exc_info=True)

    # --- エラーファイル一覧を記録 ---
    if error_files:
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(f"処理失敗ファイル一覧 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
            f.write("\n".join(error_files))
        logger.warning(f"エラーファイル: {len(error_files)}件 -> {error_file}")

    # --- サマリー ---
    logger.info("=" * 60)
    logger.info(
        f"処理完了 | 成功: {len(all_headers)}件  "
        f"明細合計: {len(all_details)}行  "
        f"エラー: {len(error_files)}件"
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
