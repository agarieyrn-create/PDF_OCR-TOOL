"""
extractor/delivery.py
納品書専用エクストラクタ。
BaseExtractorを継承し、納品書固有のロジックをオーバーライドする。
"""
import re
import logging
from typing import Optional
from extractor.base import BaseExtractor

logger = logging.getLogger(__name__)


class DeliveryExtractor(BaseExtractor):
    """
    納品書（Delivery Note）のヘッダ・明細抽出クラス。

    納品書特有の考慮点:
        - 「出荷日」「配送先」など納品書固有フィールドを抽出可能
        - 金額が記載されないケースもある（数量・品名のみ）
    """

    def extract_header(self, text: str) -> dict:
        """ヘッダ情報を抽出（納品書固有フィールドを追加）。"""
        header = super().extract_header(text)

        # 納品書固有: 出荷日
        header["ship_date"] = self._extract_ship_date(text)

        # 納品書固有: 配送先住所
        header["ship_to"] = self._extract_ship_to(text)

        return header

    def _extract_ship_date(self, text: str) -> Optional[str]:
        """出荷日を抽出する。"""
        keywords = ["出荷日", "発送日", "Ship Date", "出荷予定日"]
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

    def _extract_ship_to(self, text: str) -> Optional[str]:
        """配送先住所を抽出する。"""
        keywords = ["お届け先", "配送先", "納品先住所", "Ship To"]
        for kw in keywords:
            pattern = rf'{re.escape(kw)}[：:　\s]*([^\n]{{1,60}})'
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()
        return None

    def _parse_detail_line(self, line: str) -> dict | None:
        """
        納品書は金額なしで数量のみの明細も多いため、
        数量だけでも抽出できるよう基底クラスの処理を緩和する。
        """
        detail = super()._parse_detail_line(line)
        return detail
