"""
create_sample_pdf.py
テスト用のサンプルPDFを input/ フォルダに生成するスクリプト。

使用方法:
    python create_sample_pdf.py

必要ライブラリ:
    pip install reportlab
"""
import os
import sys

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import mm
except ImportError:
    print("reportlabが必要です: pip install reportlab")
    sys.exit(1)


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# フォント設定（日本語対応）
def _register_font():
    """システムに存在する日本語フォントを登録する。"""
    font_candidates = [
        ("/usr/share/fonts/truetype/fonts-japanese-gothic.ttf", "Gothic"),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSans"),
        ("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", "Hiragino"),
        ("C:/Windows/Fonts/msgothic.ttc", "MSGothic"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu"),
    ]
    for path, name in font_candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return None


def _draw_text(c, x, y, text, font, size=10):
    c.setFont(font, size)
    c.drawString(x, y, text)


def create_invoice_pdf(filename: str) -> None:
    """サンプル請求書PDFを生成する。"""
    path = os.path.join(OUTPUT_DIR, filename)
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    font = _register_font() or "Helvetica"

    # タイトル
    _draw_text(c, 220, h - 60, "請 求 書", font, 20)

    # ヘッダ情報
    _draw_text(c, 50,  h - 120, "株式会社サンプル商事　御中", font, 12)
    _draw_text(c, 350, h - 100, "請求書番号: INV-2024-001", font, 10)
    _draw_text(c, 350, h - 118, "請求日: 2024年3月31日",     font, 10)
    _draw_text(c, 350, h - 136, "支払期限: 2024年4月30日",   font, 10)

    _draw_text(c, 50,  h - 160, "発行者: 株式会社テスト電子",     font, 10)
    _draw_text(c, 50,  h - 178, "振込先: ○○銀行 渋谷支店 普通 1234567", font, 10)

    # 明細テーブルヘッダ
    y = h - 230
    _draw_text(c, 50,  y, "品名",         font, 10)
    _draw_text(c, 250, y, "数量",         font, 10)
    _draw_text(c, 320, y, "単価",         font, 10)
    _draw_text(c, 420, y, "金額",         font, 10)
    c.line(50, y - 5, 530, y - 5)

    # 明細行
    items = [
        ("Webシステム開発費",   1,   500000,  500000),
        ("サーバー設定作業",    2,    80000,  160000),
        ("テスト・検証費用",    1,   120000,  120000),
        ("マニュアル作成",      3,    15000,   45000),
    ]
    y -= 20
    for name, qty, unit, amount in items:
        _draw_text(c, 50,  y, name,                 font, 10)
        _draw_text(c, 250, y, str(qty),             font, 10)
        _draw_text(c, 310, y, f"{unit:,}",          font, 10)
        _draw_text(c, 410, y, f"{amount:,}",        font, 10)
        y -= 18

    # 合計
    c.line(50, y - 5, 530, y - 5)
    subtotal = sum(a for _, _, _, a in items)
    tax      = int(subtotal * 0.10)
    total    = subtotal + tax

    y -= 25
    _draw_text(c, 350, y,      "小計:",           font, 10)
    _draw_text(c, 450, y,      f"￥{subtotal:,}", font, 10)
    y -= 18
    _draw_text(c, 350, y,      "消費税(10%):",    font, 10)
    _draw_text(c, 450, y,      f"￥{tax:,}",      font, 10)
    y -= 18
    _draw_text(c, 350, y,      "請求金額:",        font, 12)
    _draw_text(c, 450, y,      f"￥{total:,}",    font, 12)

    c.save()
    print(f"作成: {path}")


def create_delivery_pdf(filename: str) -> None:
    """サンプル納品書PDFを生成する。"""
    path = os.path.join(OUTPUT_DIR, filename)
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    font = _register_font() or "Helvetica"

    _draw_text(c, 220, h - 60, "納 品 書", font, 20)

    _draw_text(c, 50,  h - 120, "株式会社サンプル商事　御中",     font, 12)
    _draw_text(c, 350, h - 100, "納品書番号: DN-2024-001",       font, 10)
    _draw_text(c, 350, h - 118, "納品日: 2024年3月25日",         font, 10)
    _draw_text(c, 350, h - 136, "出荷日: 2024年3月24日",         font, 10)

    _draw_text(c, 50,  h - 160, "納品先: 東京都渋谷区○○1-2-3", font, 10)

    y = h - 210
    _draw_text(c, 50,  y, "品名",     font, 10)
    _draw_text(c, 250, y, "数量",     font, 10)
    _draw_text(c, 320, y, "単価",     font, 10)
    _draw_text(c, 420, y, "金額",     font, 10)
    c.line(50, y - 5, 530, y - 5)

    items = [
        ("ノートPC Model-X",   5, 120000, 600000),
        ("マウス Type-B",      5,   2500,  12500),
        ("キーボード Type-C",  5,   5000,  25000),
    ]
    y -= 20
    for name, qty, unit, amount in items:
        _draw_text(c, 50,  y, name,          font, 10)
        _draw_text(c, 250, y, str(qty),      font, 10)
        _draw_text(c, 310, y, f"{unit:,}",   font, 10)
        _draw_text(c, 410, y, f"{amount:,}", font, 10)
        y -= 18

    c.line(50, y - 5, 530, y - 5)
    total = sum(a for _, _, _, a in items)
    y -= 25
    _draw_text(c, 350, y, "合計金額:", font, 12)
    _draw_text(c, 450, y, f"￥{total:,}", font, 12)

    c.save()
    print(f"作成: {path}")


def create_order_pdf(filename: str) -> None:
    """サンプル発注書PDFを生成する。"""
    path = os.path.join(OUTPUT_DIR, filename)
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    font = _register_font() or "Helvetica"

    _draw_text(c, 220, h - 60, "発 注 書", font, 20)

    _draw_text(c, 50,  h - 120, "株式会社テスト電子　御中",        font, 12)
    _draw_text(c, 350, h - 100, "発注書番号: PO-2024-001",        font, 10)
    _draw_text(c, 350, h - 118, "発注日: 2024年3月20日",          font, 10)
    _draw_text(c, 350, h - 136, "納期: 2024年4月10日",            font, 10)

    _draw_text(c, 50,  h - 160, "発注先: 株式会社テスト電子",      font, 10)
    _draw_text(c, 50,  h - 178, "発注元: 株式会社サンプル商事",    font, 10)

    y = h - 220
    _draw_text(c, 50,  y, "品名",     font, 10)
    _draw_text(c, 250, y, "数量",     font, 10)
    _draw_text(c, 320, y, "単価",     font, 10)
    _draw_text(c, 420, y, "金額",     font, 10)
    c.line(50, y - 5, 530, y - 5)

    items = [
        ("業務システム開発",   1,  800000, 800000),
        ("データ移行作業",     1,  200000, 200000),
        ("研修・トレーニング", 2,   50000, 100000),
    ]
    y -= 20
    for name, qty, unit, amount in items:
        _draw_text(c, 50,  y, name,          font, 10)
        _draw_text(c, 250, y, str(qty),      font, 10)
        _draw_text(c, 310, y, f"{unit:,}",   font, 10)
        _draw_text(c, 410, y, f"{amount:,}", font, 10)
        y -= 18

    c.line(50, y - 5, 530, y - 5)
    subtotal = sum(a for _, _, _, a in items)
    tax      = int(subtotal * 0.10)
    total    = subtotal + tax
    y -= 25
    _draw_text(c, 350, y, "発注金額:", font, 12)
    _draw_text(c, 450, y, f"￥{total:,}", font, 12)

    c.save()
    print(f"作成: {path}")


if __name__ == "__main__":
    print("サンプルPDFを生成します...")
    create_invoice_pdf("sample_invoice.pdf")
    create_delivery_pdf("sample_delivery.pdf")
    create_order_pdf("sample_order.pdf")
    print("完了。input/ フォルダに保存しました。")
    print("次のコマンドで処理を実行してください:")
    print("  python main.py")
