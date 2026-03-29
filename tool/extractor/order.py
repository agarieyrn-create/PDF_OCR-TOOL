"""
extractor/order.py
発注書専用エクストラクタ。
BaseExtractorを継承し、発注書固有のロジックをオーバーライドする。
"""
import re
import logging
from typing import Optional
from extractor.base import BaseExtractor

logger = logging.getLogger(__name__)


class OrderExtractor(BaseExtractor):
    """
    発注書（Purchase Order）のヘッダ・明細抽出クラス。

    発注書特有の考慮点:
        - 「納期」「発注先」など発注書固有フィールドを抽出可能
        - 数量・単価が重要で、合計金額が省略されることもある
    """

    def extract_header(self, text: str) -> dict:
        """ヘッダ情報を抽出（発注書固有フィールドを追加）。"""
        header = super().extract_header(text)

        # 発注書固有: 納期
        header["delivery_date"] = self._extract_delivery_date(text)

        # 発注書固有: 発注先
        header["vendor"] = self._extract_vendor(text)

        return header

    def _extract_delivery_date(self, text: str) -> Optional[str]:
        """納期を抽出する。"""
        keywords = ["納期", "納入期限", "希望納期", "Delivery Date", "納入日"]
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

    def _extract_vendor(self, text: str) -> Optional[str]:
        """発注先（仕入先）を抽出する。"""
        keywords = ["発注先", "仕入先", "納入先", "Vendor", "Supplier"]
        corp_pattern = r'(?:株式会社|有限会社|合同会社|㈱|㈲)'

        for kw in keywords:
            pattern = rf'{re.escape(kw)}[：:　\s\n]*([^\n]{{1,40}}{corp_pattern}[^\n]*)'
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()
        return None
