"""
extractor/base.py
全ドキュメント種別に共通する抽出ロジックを提供する基底クラス。
ヘッダ抽出・明細抽出・金額パースなどを実装。
各ドキュメント種別のクラスはこれを継承して差分のみオーバーライドする。
"""
import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ユーティリティ関数
# ---------------------------------------------------------------------------

def parse_amount(text: str) -> Optional[int]:
    """
    金額文字列を整数に変換する。

    対応フォーマット:
        12345 / 12,345 / ￥12,345 / ¥12,345
        -12,345 / △12,345 / ▲12,345（マイナス）
        小数点付き（123.00 -> 123）
    """
    if not text:
        return None
    s = str(text).strip()

    # マイナス判定
    negative = bool(re.match(r'^[-△▲]', s))
    s = re.sub(r'^[-△▲]', '', s)

    # 通貨記号・空白を除去
    s = re.sub(r'[￥¥\s]', '', s)

    # カンマを除去
    s = s.replace(',', '')

    # 小数点以下を切り捨て
    s = re.sub(r'\.\d+$', '', s)

    # 数値部分を抽出
    m = re.search(r'\d+', s)
    if not m:
        return None

    val = int(m.group())
    return -val if negative else val


# ---------------------------------------------------------------------------
# 基底エクストラクタ
# ---------------------------------------------------------------------------

class BaseExtractor:
    """
    ヘッダ情報と明細情報の抽出基底クラス。

    ルールJSONの構造:
        classification_keywords: [str]
        header:
            date:    [str]  # 日付を示すキーワード
            amount:  [str]  # 金額を示すキーワード
            company: [str]  # 会社名を示すキーワード
            number:  [str]  # 番号を示すキーワード
        detail_start_keywords: [str]
        detail_end_keywords:   [str]
    """

    def __init__(self, rules_file: str) -> None:
        with open(rules_file, encoding="utf-8") as f:
            self.rules: dict = json.load(f)
        logger.debug(f"ルール読み込み: {rules_file}")

    # ------------------------------------------------------------------
    # パブリックAPI
    # ------------------------------------------------------------------

    def extract_header(self, text: str) -> dict:
        """ヘッダ情報を抽出して辞書で返す。"""
        return {
            "date":    self._extract_date(text),
            "amount":  self._extract_amount(text),
            "company": self._extract_company(text),
            "number":  self._extract_number(text),
        }

    def extract_details(self, text: str) -> list[dict]:
        """明細行を抽出してリストで返す。"""
        start_keywords = self.rules.get("detail_start_keywords", [])
        end_keywords   = self.rules.get("detail_end_keywords", [])

        lines = text.splitlines()
        start_idx = self._find_detail_start(lines, start_keywords)
        if start_idx is None:
            logger.debug("明細開始キーワードが見つかりませんでした")
            return []

        details = []
        for line in lines[start_idx:]:
            stripped = line.strip()
            if not stripped:
                continue
            # 終了キーワードで打ち切り
            if any(kw in stripped for kw in end_keywords):
                break
            # 数値が含まれる行のみ明細候補
            if not re.search(r'\d', stripped):
                continue

            detail = self._parse_detail_line(stripped)
            if detail:
                details.append(detail)

        return details

    # ------------------------------------------------------------------
    # ヘッダ抽出の内部メソッド
    # ------------------------------------------------------------------

    def _extract_date(self, text: str) -> Optional[str]:
        """日付を抽出する。キーワード近傍を優先し、なければ全文から検索。"""
        keywords = self.rules.get("header", {}).get("date", [])

        # キーワード直後の日付を探す
        for kw in keywords:
            pattern = (
                rf'{re.escape(kw)}'
                rf'[：:　\s]*'
                rf'(\d{{4}}[年/\-]\d{{1,2}}[月/\-]\d{{1,2}}日?'
                rf'|令和\d+年\d{{1,2}}月\d{{1,2}}日'
                rf'|R\d+\.\d+\.\d+)'
            )
            m = re.search(pattern, text)
            if m:
                return m.group(1)

        # フォールバック: 全文から一般的な日付パターンを検索
        date_patterns = [
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{4}/\d{1,2}/\d{1,2})',
            r'(\d{4}-\d{1,2}-\d{1,2})',
            r'(令和\d+年\d{1,2}月\d{1,2}日)',
            r'(R\d+\.\d+\.\d+)',
        ]
        for pat in date_patterns:
            m = re.search(pat, text)
            if m:
                return m.group(1)

        return None

    def _extract_amount(self, text: str) -> Optional[int]:
        """金額をキーワード近傍から抽出する。"""
        keywords = self.rules.get("header", {}).get("amount", [])
        amount_re = r'([△▲-]?[￥¥]?\s*[\d,]+(?:\.\d+)?)'

        for kw in keywords:
            pattern = rf'{re.escape(kw)}[：:　\s]*{amount_re}'
            m = re.search(pattern, text)
            if m:
                return parse_amount(m.group(1))

        return None

    def _extract_company(self, text: str) -> Optional[str]:
        """会社名をキーワード近傍または法人格パターンから抽出する。"""
        keywords = self.rules.get("header", {}).get("company", [])
        corp_re = r'(?:株式会社|有限会社|合同会社|一般社団法人|㈱|㈲)'

        for kw in keywords:
            # Pattern 1: 「発注先: 株式会社○○」- キーワードの後に会社名
            # {0,20} で「株式会社」が先頭に来る場合も対応
            pattern = rf'{re.escape(kw)}[：:　\s\n]*([^\n]{{0,20}}{corp_re}[^\n]{{0,30}})'
            m = re.search(pattern, text)
            if m:
                name = re.sub(r'^[：:\s　]+', '', m.group(1)).strip()
                if name:
                    return name

            # Pattern 2: 「○○株式会社 御中」- 会社名の後にキーワード
            pattern2 = rf'({corp_re}[^\n]{{1,30}})\s*{re.escape(kw)}'
            m2 = re.search(pattern2, text)
            if m2:
                return m2.group(1).strip()

        # フォールバック: 法人格から始まる最初の行
        m = re.search(rf'({corp_re}[^\n]{{0,30}})', text)
        if m:
            return m.group(1).strip()

        return None

    def _extract_number(self, text: str) -> Optional[str]:
        """ドキュメント番号をキーワード近傍から抽出する。"""
        keywords = self.rules.get("header", {}).get("number", [])

        for kw in keywords:
            pattern = rf'{re.escape(kw)}[：:\s\-#]*([A-Za-z0-9\-_/]+)'
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()

        return None

    # ------------------------------------------------------------------
    # 明細抽出の内部メソッド
    # ------------------------------------------------------------------

    def _find_detail_start(self, lines: list[str], keywords: list[str]) -> Optional[int]:
        """明細ヘッダ行のインデックスを返す（次行から明細が始まる）。"""
        for i, line in enumerate(lines):
            if any(kw in line for kw in keywords):
                return i + 1
        return None

    def _parse_detail_line(self, line: str) -> Optional[dict]:
        """
        1行の明細テキストを解析して辞書で返す。

        行末側の連続する数値を 金額・単価・数量 の順に割り当てる方式。
        （日本の帳票は右端から「数量 単価 金額」の順が多い）
        """
        # 数値トークンをすべて抽出
        number_tokens = re.findall(r'[△▲-]?[￥¥]?[\d,]+(?:\.\d+)?', line)
        if not number_tokens:
            return None

        # 数値部分を除去して品名を取得
        name_part = re.sub(r'[△▲-]?[￥¥]?[\d,]+(?:\.\d+)?\s*', '', line).strip()
        # 品名が空・または記号だけの場合はスキップ
        if not name_part or re.fullmatch(r'[\s\W]+', name_part):
            return None

        parsed = [parse_amount(t) for t in number_tokens if parse_amount(t) is not None]

        detail: dict = {
            "name":       name_part,
            "quantity":   None,
            "unit_price": None,
            "amount":     None,
        }

        if len(parsed) >= 3:
            detail["quantity"]   = parsed[-3]
            detail["unit_price"] = parsed[-2]
            detail["amount"]     = parsed[-1]
        elif len(parsed) == 2:
            detail["unit_price"] = parsed[-2]
            detail["amount"]     = parsed[-1]
        elif len(parsed) == 1:
            detail["amount"] = parsed[-1]

        return detail
