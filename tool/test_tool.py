"""
test_tool.py
ツールの各モジュールを単体テストするスクリプト。
外部ライブラリへの依存を最小限にし、コアロジックを検証する。

使用方法:
    python test_tool.py
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

# ANSI カラー
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
RESET = "\033[0m"

passed_all: list[bool] = []


def check(name: str, ok: bool, detail: str = ""):
    passed_all.append(ok)
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    line = f"  [{mark}] {name}"
    if detail and not ok:
        line += f"  ({detail})"
    print(line)


def section(title: str):
    print(f"\n{YELLOW}=== {title} ==={RESET}")


# ---------------------------------------------------------------------------
# parse_amount
# ---------------------------------------------------------------------------
section("parse_amount")
from extractor.base import parse_amount

check("整数",           parse_amount("12345")     == 12345)
check("カンマ区切り",   parse_amount("12,345")    == 12345)
check("全角円マーク",   parse_amount("￥12,345")  == 12345)
check("半角円マーク",   parse_amount("¥12,345")   == 12345)
check("マイナス記号",   parse_amount("-12,345")   == -12345)
check("△マイナス",      parse_amount("△12,345")  == -12345)
check("▲マイナス",      parse_amount("▲1,000")   == -1000)
check("小数点切り捨て", parse_amount("1,234.00")  == 1234)
check("空文字 -> None", parse_amount("")          is None)
check("None -> None",   parse_amount(None)        is None)
check("文字のみ->None", parse_amount("abc")       is None)
check("大きな金額",     parse_amount("1,234,567") == 1234567)


# ---------------------------------------------------------------------------
# classify_document
# ---------------------------------------------------------------------------
section("classify_document")
from classifier import classify_document, clear_cache

rules_dir = os.path.join(os.path.dirname(__file__), "rules")

if os.path.isdir(rules_dir):
    tests = [
        ("請求書分類",   "請求書\n請求金額 ￥100,000\n支払期限 2024年4月30日\n振込先",      "invoice"),
        ("納品書分類",   "納品書\n納品日 2024年3月25日\n納品書番号 DN-001\nお届け先",       "delivery"),
        ("発注書分類",   "発注書\n発注番号 PO-001\n納期 2024年4月10日\nご発注",             "order"),
        ("unknown分類", "これはどの種別にも当てはまらないテキストです",                     "unknown"),
    ]
    for name, text, expected in tests:
        clear_cache()
        result = classify_document(text, rules_dir)
        check(name, result == expected, f"期待={expected}, 実際={result}")
else:
    print(f"  [SKIP] rulesディレクトリが見つかりません: {rules_dir}")


# ---------------------------------------------------------------------------
# BaseExtractor ヘッダ抽出
# ---------------------------------------------------------------------------
section("BaseExtractor.extract_header")

rules_file = os.path.join(rules_dir, "invoice.json")
if os.path.exists(rules_file):
    from extractor.base import BaseExtractor

    ext = BaseExtractor(rules_file)

    SAMPLE = """
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

    h = ext.extract_header(SAMPLE)
    check("日付抽出",   h["date"]    is not None,         f"got: {h['date']}")
    check("金額抽出",   h["amount"]  is not None,         f"got: {h['amount']}")
    check("会社名抽出", h["company"] is not None,         f"got: {h['company']}")
    check("番号抽出",   h["number"]  is not None,         f"got: {h['number']}")
    check("日付の値",   "2024" in str(h.get("date", "")), f"got: {h['date']}")
    check("金額の値",   h.get("amount") == 825000,        f"got: {h['amount']}")


# ---------------------------------------------------------------------------
# BaseExtractor 明細抽出
# ---------------------------------------------------------------------------
section("BaseExtractor.extract_details")

if os.path.exists(rules_file):
    details = ext.extract_details(SAMPLE)
    check("明細件数 > 0",    len(details) > 0,                       f"got: {len(details)}")
    check("品名あり",        details[0].get("name") is not None,     f"got: {details[0]}")
    check("金額あり",        details[0].get("amount") is not None,   f"got: {details[0]}")


# ---------------------------------------------------------------------------
# _parse_detail_line パターン
# ---------------------------------------------------------------------------
section("_parse_detail_line")

if os.path.exists(rules_file):
    # 数量・単価・金額の3数値
    d = ext._parse_detail_line("システム開発費  1  500,000  500,000")
    check("3数値: 数量",      d is not None and d["quantity"]   == 1)
    check("3数値: 単価",      d is not None and d["unit_price"] == 500000)
    check("3数値: 金額",      d is not None and d["amount"]     == 500000)

    # 単価・金額の2数値
    d2 = ext._parse_detail_line("コンサルティング費用  80,000  80,000")
    check("2数値: 金額あり",  d2 is not None and d2["amount"]   == 80000)

    # 金額のみ
    d3 = ext._parse_detail_line("一式作業費  ￥150,000")
    check("1数値: 金額あり",  d3 is not None and d3["amount"]   == 150000)

    # 数値なし -> None
    d4 = ext._parse_detail_line("これは数値なしの行です")
    check("数値なし -> None", d4 is None)

    # マイナス金額
    d5 = ext._parse_detail_line("値引き  △10,000")
    check("マイナス金額",     d5 is not None and d5["amount"] == -10000,
          f"got: {d5}")


# ---------------------------------------------------------------------------
# ProcessResult データクラス
# ---------------------------------------------------------------------------
section("ProcessResult")
from main import ProcessResult, results_to_excel_rows
from pathlib import Path

r1 = ProcessResult(
    pdf_path=Path("invoice_001.pdf"),
    status="success", doc_type="invoice",
    header={"date": "2024年3月31日", "amount": 100000,
            "company": "株式会社テスト", "number": "INV-001"},
    details=[{"name": "開発費", "quantity": 1, "unit_price": 100000, "amount": 100000}],
)
r2 = ProcessResult(
    pdf_path=Path("unknown.pdf"),
    status="unknown", doc_type="unknown",
    header={}, details=[],
)
r3 = ProcessResult(
    pdf_path=Path("error.pdf"),
    status="error", doc_type="unknown",
    error_msg="テキスト抽出失敗",
)

check("status=success", r1.status == "success")
check("details 件数",   len(r1.details) == 1)
check("error_msg",      r3.error_msg == "テキスト抽出失敗")

headers, details = results_to_excel_rows([r1, r2, r3])
check("ヘッダ行数",     len(headers) == 3,    f"got: {len(headers)}")
check("明細行数",       len(details) == 1,    f"got: {len(details)}")
check("ヘッダ[0]金額",  headers[0][3] == 100000)
check("ヘッダ[1]種類",  headers[1][1] == "不明")
check("明細[0]品名",    details[0][2] == "開発費")


# ---------------------------------------------------------------------------
# GUIモジュール インポート確認
# ---------------------------------------------------------------------------
section("GUI インポート")

try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()

    import gui
    check("gui.py インポート", True)

    app = gui.PDFOCRApp(root)
    check("PDFOCRApp 生成",    True)

    root.destroy()
except ImportError:
    # ヘッドレス環境（CI等）では tkinter が使えないため SKIP
    passed_all.append(True)
    print(f"  [{YELLOW}SKIP{RESET}] GUI インポート (tkinter 未利用環境)")
    passed_all.append(True)
    print(f"  [{YELLOW}SKIP{RESET}] PDFOCRApp 生成 (tkinter 未利用環境)")
except Exception as e:
    check("PDFOCRApp 生成", False, str(e))


# ---------------------------------------------------------------------------
# config.json 読み込み
# ---------------------------------------------------------------------------
section("config.json")

config_path = os.path.join(os.path.dirname(__file__), "config.json")
if os.path.exists(config_path):
    from main import load_config
    cfg = load_config(config_path)
    check("input_dir キー存在",    "input_dir"    in cfg)
    check("output_dir キー存在",   "output_dir"   in cfg)
    check("ocr_language キー存在", "ocr_language" in cfg)
    check("ocr_dpi キー存在",      "ocr_dpi"      in cfg)
else:
    print("  [SKIP] config.json が見つかりません")


# ---------------------------------------------------------------------------
# 結果サマリー
# ---------------------------------------------------------------------------
print(f"\n{'=' * 44}")
passed = sum(1 for r in passed_all if r)
total  = len(passed_all)
color  = GREEN if passed == total else YELLOW
print(f"{color}結果: {passed} / {total} テスト通過{RESET}")
if passed < total:
    print(f"{RED}失敗: {total - passed}件{RESET}")
    sys.exit(1)
