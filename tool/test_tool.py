"""
test_tool.py
ツールの各モジュールを単体テストするスクリプト。
外部ライブラリなしで動作確認できるように設計。

使用方法:
    python test_tool.py
"""
import os
import sys
import json
import tempfile

# パスを通す
sys.path.insert(0, os.path.dirname(__file__))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append(condition)
    msg = f"  [{status}] {name}"
    if detail and not condition:
        msg += f" - {detail}"
    print(msg)


# ---------------------------------------------------------------------------
# parse_amount テスト
# ---------------------------------------------------------------------------

print("\n=== parse_amount ===")
from extractor.base import parse_amount

check("整数",           parse_amount("12345")       == 12345)
check("カンマ付き",     parse_amount("12,345")      == 12345)
check("円マーク",       parse_amount("￥12,345")    == 12345)
check("¥マーク",        parse_amount("¥12,345")     == 12345)
check("マイナス",       parse_amount("-12,345")     == -12345)
check("△マイナス",      parse_amount("△12,345")    == -12345)
check("▲マイナス",      parse_amount("▲1,000")     == -1000)
check("小数点付き",     parse_amount("1,234.00")    == 1234)
check("空文字",         parse_amount("")            is None)
check("None",           parse_amount(None)          is None)
check("文字のみ",       parse_amount("abc")         is None)


# ---------------------------------------------------------------------------
# classifier テスト
# ---------------------------------------------------------------------------

print("\n=== classify_document ===")
from classifier import classify_document, clear_cache

rules_dir = os.path.join(os.path.dirname(__file__), "rules")

if os.path.isdir(rules_dir):
    clear_cache()
    invoice_text = "請求書\n請求金額 ￥100,000\n支払期限 2024年4月30日"
    check("請求書分類",   classify_document(invoice_text, rules_dir) == "invoice")

    clear_cache()
    delivery_text = "納品書\n納品日 2024年3月25日\n納品書番号 DN-001"
    check("納品書分類",   classify_document(delivery_text, rules_dir) == "delivery")

    clear_cache()
    order_text = "発注書\n発注番号 PO-001\n納期 2024年4月10日"
    check("発注書分類",   classify_document(order_text, rules_dir) == "order")

    clear_cache()
    unknown_text = "これはテキストです"
    check("unknown分類", classify_document(unknown_text, rules_dir) == "unknown")
else:
    print(f"  [SKIP] rulesディレクトリが見つかりません: {rules_dir}")


# ---------------------------------------------------------------------------
# BaseExtractor テスト
# ---------------------------------------------------------------------------

print("\n=== BaseExtractor ===")

rules_file = os.path.join(rules_dir, "invoice.json")
if os.path.exists(rules_file):
    from extractor.base import BaseExtractor

    ext = BaseExtractor(rules_file)

    sample_text = """
    株式会社サンプル商事　御中

    請求書番号: INV-2024-001
    請求日: 2024年3月31日
    請求金額: ￥825,000

    品名　　　数量　単価　　金額
    Webシステム開発費　1　500,000　500,000
    サーバー設定作業　2　80,000　160,000
    小計
    合計: ￥825,000
    """

    header = ext.extract_header(sample_text)
    check("日付抽出",   header["date"] is not None,   f"got: {header['date']}")
    check("金額抽出",   header["amount"] is not None, f"got: {header['amount']}")
    check("会社名抽出", header["company"] is not None, f"got: {header['company']}")
    check("番号抽出",   header["number"] is not None,  f"got: {header['number']}")

    details = ext.extract_details(sample_text)
    check("明細抽出",   len(details) > 0, f"got: {len(details)}件")
    if details:
        check("品名あり",   details[0]["name"] is not None)
        check("金額あり",   details[0]["amount"] is not None)
else:
    print(f"  [SKIP] {rules_file} が見つかりません")


# ---------------------------------------------------------------------------
# _parse_detail_line テスト
# ---------------------------------------------------------------------------

print("\n=== _parse_detail_line ===")
if os.path.exists(rules_file):
    ext = BaseExtractor(rules_file)

    # 数量・単価・金額が揃っているケース
    d = ext._parse_detail_line("システム開発費  1  500,000  500,000")
    check("3数値: 数量",      d and d["quantity"]   == 1)
    check("3数値: 単価",      d and d["unit_price"] == 500000)
    check("3数値: 金額",      d and d["amount"]     == 500000)

    # 単価・金額のみ
    d2 = ext._parse_detail_line("コンサルティング費用  80,000  80,000")
    check("2数値: 金額",      d2 and d2["amount"] == 80000)

    # 数値なし -> None
    d3 = ext._parse_detail_line("これは数値なしの行")
    check("数値なし -> None", d3 is None)


# ---------------------------------------------------------------------------
# 結果サマリー
# ---------------------------------------------------------------------------

print(f"\n{'=' * 40}")
passed = sum(1 for r in results if r)
total  = len(results)
color  = "\033[92m" if passed == total else "\033[93m"
print(f"{color}結果: {passed}/{total} テスト通過\033[0m")

if passed < total:
    sys.exit(1)
