"""
classifier.py
テキスト内のキーワード一致数によってドキュメント種別を判定するモジュール。
ルールはrules/配下のJSONから動的に読み込むため、新カテゴリ追加が容易。
"""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ルールのキャッシュ（同一実行内で何度も読まないための最適化）
_rules_cache: dict = {}


def load_classification_rules(rules_dir: str) -> dict[str, list[str]]:
    """
    rules_dir 内の全JSONファイルから分類キーワードを読み込む。

    Returns:
        {doc_type: [keyword, ...]} の辞書
    """
    global _rules_cache
    cache_key = rules_dir

    if cache_key in _rules_cache:
        return _rules_cache[cache_key]

    rules: dict[str, list[str]] = {}
    if not os.path.isdir(rules_dir):
        logger.error(f"rulesディレクトリが見つかりません: {rules_dir}")
        return rules

    for fname in os.listdir(rules_dir):
        if not fname.endswith(".json"):
            continue
        doc_type = fname.replace(".json", "")
        fpath = os.path.join(rules_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            keywords = data.get("classification_keywords", [])
            rules[doc_type] = keywords
            logger.debug(f"ルール読み込み: {doc_type} ({len(keywords)}件)")
        except Exception as e:
            logger.warning(f"ルールファイル読み込み失敗 ({fpath}): {e}")

    _rules_cache[cache_key] = rules
    return rules


def classify_document(text: str, rules_dir: str) -> str:
    """
    テキストを解析してドキュメント種別を返す。

    スコアリング方式:
        各カテゴリのキーワードリストと照合し、一致数が最大のカテゴリを採用。
        同点の場合は最初に見つかったものを優先。
        いずれも 0 点の場合は "unknown" を返す。

    Args:
        text:      抽出済みテキスト
        rules_dir: ルールJSONが置かれたディレクトリ

    Returns:
        "invoice" | "delivery" | "order" | "unknown"
    """
    rules = load_classification_rules(rules_dir)
    if not rules:
        logger.warning("分類ルールが空です")
        return "unknown"

    scores: dict[str, int] = {}
    for doc_type, keywords in rules.items():
        score = sum(1 for kw in keywords if kw in text)
        scores[doc_type] = score

    logger.info(f"分類スコア: {scores}")

    max_score = max(scores.values())
    if max_score == 0:
        logger.warning("全カテゴリのスコアが0 -> unknown")
        return "unknown"

    best = max(scores, key=lambda k: scores[k])
    return best


def clear_cache() -> None:
    """ルールキャッシュをクリアする（テスト時などに使用）。"""
    global _rules_cache
    _rules_cache = {}
