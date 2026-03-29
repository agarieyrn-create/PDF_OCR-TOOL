"""
ocr.py
画像PDFに対してOCRを実行するモジュール。
pdf2imageでPDFを画像変換し、pytesseractでOCR処理する。
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def ocr_pdf(pdf_path: str, language: str = "jpn+eng", dpi: int = 300) -> str:
    """
    PDFを画像に変換してOCRを実行する。

    Args:
        pdf_path:  PDFファイルのパス
        language:  Tesseractの言語設定（例: "jpn+eng"）
        dpi:       変換時の解像度（高いほど精度UP・処理時間増）

    Returns:
        OCRで得たテキスト。失敗時は空文字列。
    """
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as e:
        logger.error(f"必要なライブラリが不足しています: {e}")
        logger.error("pip install pdf2image pytesseract を実行してください")
        return ""

    try:
        logger.info(f"OCR開始: {pdf_path} (DPI={dpi}, lang={language})")
        images = convert_from_path(pdf_path, dpi=dpi)
        pages_text = []

        for i, image in enumerate(images):
            # 画像前処理: グレースケール変換で認識精度向上
            gray = _preprocess_image(image)
            text = pytesseract.image_to_string(gray, lang=language)
            pages_text.append(text)
            logger.debug(f"OCR ページ{i + 1}/{len(images)} 完了: {len(text)}文字")

        result = "\n".join(pages_text)
        logger.info(f"OCR完了: {pdf_path} ({len(result)}文字)")
        return result

    except Exception as e:
        logger.error(f"OCR失敗 ({pdf_path}): {e}")
        return ""


def _preprocess_image(image):
    """
    OCR精度向上のための画像前処理。
    グレースケール変換のみ行うシンプルな実装。
    """
    try:
        return image.convert("L")
    except Exception:
        return image
