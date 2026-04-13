"""
pdf_reader.py
PDFからテキストを抽出するモジュール。

主な工夫:
    - PyMuPDFのword-level座標情報を使い、テーブルの行を正しく再構築する
    - 同じY座標付近の単語を1行にまとめることで
      「カラムが別行になる」問題を解消する
    - フォールバックとして pdfplumber にも対応
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 同じ行と見なすY座標の許容誤差（ポイント）
ROW_Y_TOLERANCE = 4.0

# 単語間に挿入するスペース（ポイント単位の閾値）
WORD_SPACE_THRESHOLD = 6.0


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    PDFからテキストを抽出する。テーブルレイアウトも正しく行として再構築する。

    Args:
        pdf_path: PDFファイルのパス

    Returns:
        抽出テキスト。失敗時は空文字列。
    """
    # --- PyMuPDF を優先使用（座標ベースで行を再構築） ---
    try:
        import fitz  # PyMuPDF

        pages_text = []
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                text = _extract_page_text_fitz(page)
                if text.strip():
                    pages_text.append(text)
                    logger.debug(f"ページ{i + 1} テキスト抽出 (PyMuPDF): {len(text)}文字")

        result = "\n".join(pages_text)
        if result.strip():
            logger.debug(f"PyMuPDF 抽出完了: {pdf_path} ({len(result)}文字)")
            return result

    except ImportError:
        logger.debug("PyMuPDF未インストール、pdfplumberを試みます")
    except Exception as e:
        logger.warning(f"PyMuPDF 抽出失敗 ({pdf_path}): {e}")

    # --- フォールバック: pdfplumber ---
    try:
        import pdfplumber

        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(text)
                    logger.debug(f"ページ{i + 1} テキスト抽出 (pdfplumber): {len(text)}文字")

        result = "\n".join(pages_text)
        logger.debug(f"pdfplumber 抽出完了: {pdf_path} ({len(result)}文字)")
        return result

    except ImportError:
        logger.debug("pdfplumber未インストール")
    except Exception as e:
        logger.warning(f"pdfplumber 抽出失敗 ({pdf_path}): {e}")

    logger.warning(f"テキスト抽出失敗（OCRにフォールバック）: {pdf_path}")
    return ""


def _extract_page_text_fitz(page) -> str:
    """
    PyMuPDFページからword-level座標情報を使って、
    テーブル行を正しく再構築したテキストを返す。

    get_text("words") が返すタプルの構造:
        (x0, y0, x1, y1, "word", block_no, line_no, word_no)
    """
    words = page.get_text("words")
    if not words:
        return ""

    # Y座標でソート（上から下）、同じ行は X座標でソート（左から右）
    words_sorted = sorted(words, key=lambda w: (round(w[1] / ROW_Y_TOLERANCE), w[0]))

    lines: list[str] = []
    current_row_words: list[tuple] = []
    current_y: Optional[float] = None

    def flush_row():
        """溜めた単語を1行のテキストとして確定する。"""
        if not current_row_words:
            return
        # X座標でソートして行テキストを構築
        row_sorted = sorted(current_row_words, key=lambda w: w[0])
        row_text_parts = []
        prev_x1 = None
        for w in row_sorted:
            x0, _, x1, _, word_text = w[0], w[1], w[2], w[3], w[4]
            if prev_x1 is not None and (x0 - prev_x1) > WORD_SPACE_THRESHOLD:
                row_text_parts.append("  ")  # 列間スペース
            row_text_parts.append(word_text)
            prev_x1 = x1
        lines.append("".join(row_text_parts))

    for word in words_sorted:
        x0, y0, x1, y1, word_text = word[0], word[1], word[2], word[3], word[4]

        if current_y is None:
            current_y = y0
        elif abs(y0 - current_y) > ROW_Y_TOLERANCE:
            # Y座標が変わった = 新しい行
            flush_row()
            current_row_words = []
            current_y = y0

        current_row_words.append((x0, y0, x1, y1, word_text))

    flush_row()  # 最後の行を確定

    return "\n".join(lines)
