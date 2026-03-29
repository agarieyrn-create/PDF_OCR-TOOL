"""
extractor/invoice.py
請求書専用エクストラクタ。
BaseExtractorを継承し、請求書固有のロジックをオーバーライドする。
"""
import re
import logging
from typing import Optional
from extractor.base import BaseExtractor, parse_amount

logger = logging.getLogger(__name__)


class InvoiceExtractor(BaseExtractor):
    """
    請求書（Invoice）のヘッダ・明細抽出クラス。

    請求書特有の考慮点:
        - 「支払期限」「振込先」など請求書固有フィールドを抽出可能
        - 税込/税抜金額の両方が記載される場合は税込を優先
    """

    def extract_header(self, text: str) -> dict:
        """ヘッダ情報を抽出（請求書固有フィールドを追加）。"""
        header = super().extract_header(text)

        # 請求書固有: 支払期限
        header["due_date"] = self._extract_due_date(text)

        # 請求書固有: 振込先銀行
        header["bank_info"] = self._extract_bank_info(text)

        return header

    def _extract_amount(self, text: str) -> Optional[int]:
        """
        税込合計を優先して金額を抽出する。
        税込金額が見つからない場合は基底クラスの処理にフォールバック。
        """
        # 税込合計を最優先
        tax_included_keywords = ["税込合計", "税込金額", "ご請求金額", "お支払金額"]
        amount_re = r'([△▲-]?[￥¥]?\s*[\d,]+(?:\.\d+)?)'

        for kw in tax_included_keywords:
            pattern = rf'{re.escape(kw)}[：:　\s]*{amount_re}'
            m = re.search(pattern, text)
            if m:
                return parse_amount(m.group(1))

        return super()._extract_amount(text)

    def _extract_due_date(self, text: str) -> Optional[str]:
        """支払期限を抽出する。"""
        keywords = ["支払期限", "お支払期限", "振込期限", "Due Date"]
        for kw in keywords:
            pattern = (
                rf'{re.escape(kw)}'
                rf'[：:　\s]*'
                rf'(\d{{4}}[年/\-]\d{{1,2}}[月/\-]\d{{1,2}}日?'
                rf'|\d{{4}}/\d{{1,2}}/\d{{1,2}}'
                rf'|令和\d+年\d{{1,2}}月\d{{1,2}}日)'
            )
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        return None

    def _extract_bank_info(self, text: str) -> Optional[str]:
        """振込先の銀行情報を抽出する。"""
        keywords = ["振込先", "お振込先", "振込口座"]
        for kw in keywords:
            pattern = rf'{re.escape(kw)}[：:　\s]*([^\n]{{1,60}})'
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()
        return None
