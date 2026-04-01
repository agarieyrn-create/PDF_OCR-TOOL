"""
gui.py
PDF OCRツール GUIアプリケーション

起動方法:
    python gui.py

機能:
    - PDFファイルのドラッグ&ドロップ / フォルダ選択
    - ファイルごとのリアルタイム処理状態（色付き）
    - 抽出結果のプレビュー（ヘッダ/明細タブ）
    - 列クリックでソート
    - Excel保存ダイアログ（保存後にファイルを開くか選択）
    - ログビューア（INFO/WARNING/ERRORで色分け）
    - 設定ダイアログ（config.json を GUI から編集）
    - キーボードショートカット

任意ライブラリ:
    pip install tkinterdnd2   # ドラッグ&ドロップを有効化
"""
import os
import sys
import json
import queue
import logging
import threading
import subprocess
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import tkinter as tk
from tkinter import ttk

# ドラッグ&ドロップ（オプション）
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ツールモジュールのパスを通す
from app_path import APP_DIR as TOOL_DIR
sys.path.insert(0, str(TOOL_DIR))

from main import (
    load_config, write_excel,
    process_single_pdf, results_to_excel_rows,
    DOC_TYPE_LABELS, ProcessResult,
)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

APP_TITLE   = "PDF OCR ツール"
APP_VERSION = "1.0"
WIN_SIZE    = "1280x780"
WIN_MIN     = (860, 560)

# 状態ラベル -> (文字色, 背景色)
STATUS_STYLE: dict[str, tuple[str, str]] = {
    "待機":   ("#757575", "#F5F5F5"),
    "処理中": ("#1565C0", "#E3F2FD"),
    "完了":   ("#2E7D32", "#E8F5E9"),
    "不明":   ("#E65100", "#FFF3E0"),
    "エラー": ("#B71C1C", "#FFEBEE"),
}

ACCENT_COLOR  = "#2F5496"
ACCENT_FG     = "#FFFFFF"
APP_BG        = "#F0F2F5"
PANEL_BG      = "#FFFFFF"
LOG_BG        = "#1E1E1E"
LOG_FG        = "#D4D4D4"

# ---------------------------------------------------------------------------
# ログキューハンドラ
# ---------------------------------------------------------------------------

class _QueueHandler(logging.Handler):
    """ログレコードをキューに投入してGUIスレッドに渡す。"""
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord):
        self.q.put((record.levelname, self.format(record)))


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _fmt_amount(value) -> str:
    """金額を表示用文字列に変換する。"""
    if value is None:
        return ""
    try:
        return f"¥{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def _open_file(path: str):
    """OSに応じてファイルを開く。"""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 設定ダイアログ
# ---------------------------------------------------------------------------

class SettingsDialog(tk.Toplevel):
    """config.json をGUIから編集するダイアログ。"""

    _FIELDS = [
        ("input_dir",    "入力フォルダ",           str),
        ("output_dir",   "出力フォルダ",           str),
        ("output_file",  "出力ファイル名",          str),
        ("ocr_language", "OCR言語  例: jpn / jpn+eng", str),
        ("ocr_dpi",      "OCR DPI  精度重視: 400",  int),
    ]

    def __init__(self, parent, config_path: Path, config: dict, on_save):
        super().__init__(parent)
        self.title("設定")
        self.geometry("440x290")
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        self.config_path = config_path
        self.on_save     = on_save
        self._vars: dict[str, tuple[tk.StringVar, type]] = {}

        # --- フォームエリア ---
        form = ttk.Frame(self, padding=(20, 16, 20, 8))
        form.pack(fill=tk.BOTH, expand=True)

        for row, (key, label, typ) in enumerate(self._FIELDS):
            ttk.Label(form, text=label, anchor=tk.W).grid(
                row=row, column=0, sticky=tk.W, pady=5, padx=(0, 12))
            var = tk.StringVar(value=str(config.get(key, "")))
            ttk.Entry(form, textvariable=var, width=26).grid(
                row=row, column=1, sticky=tk.EW, pady=5)
            self._vars[key] = (var, typ)

        form.columnconfigure(1, weight=1)

        # --- ボタン ---
        btn_frame = ttk.Frame(self, padding=(20, 0, 20, 14))
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="キャンセル", command=self.destroy).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(btn_frame, text="保存", command=self._save).pack(side=tk.RIGHT)

    def _save(self):
        try:
            new_cfg: dict = {}
            for key, (var, typ) in self._vars.items():
                raw = var.get().strip()
                new_cfg[key] = typ(raw) if raw else (0 if typ is int else "")
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(new_cfg, f, ensure_ascii=False, indent=2)
            self.on_save(new_cfg)
            self.destroy()
        except Exception as e:
            messagebox.showerror("保存エラー", str(e), parent=self)


# ---------------------------------------------------------------------------
# ヘルプウィンドウ
# ---------------------------------------------------------------------------

_HELP_TEXT = """
【基本操作】
  ① ファイル追加ボタン または フォルダ選択 でPDFを登録
    （tkinterdnd2 インストール済みならドラッグ&ドロップも可能）
  ② [▶ 処理開始] をクリック（またはF5）
     ・ファイルごとにリアルタイムで状態が更新されます
  ③ 結果プレビューで内容を確認
  ④ [💾 Excel出力] で保存

【状態の色の意味】
  待機  ：処理待ち
  処理中：OCR/抽出実行中
  完了  ：正常に分類・抽出できました
  不明  ：分類できませんでした（rulesを確認）
  エラー：PDF読み込みまたは抽出で例外が発生

【キーボードショートカット】
  Ctrl+O  ファイル追加
  Ctrl+D  フォルダ選択
  F5      処理開始
  Ctrl+S  Excel出力
  Delete  選択ファイルをリストから削除

【分類ルールの変更】
  rules/ フォルダ内のJSONファイルを編集してください
    invoice.json  → 請求書
    delivery.json → 納品書
    order.json    → 発注書
  classification_keywords のリストにキーワードを追加するだけで
  スコアが上がり、分類精度が向上します。

【OCR設定】
  設定メニュー → 設定を編集 で変更できます
  ocr_language : jpn（日本語のみ）/ jpn+eng（日英混在）
  ocr_dpi      : 300（標準） / 400（高精度・低速）

  ※ Tesseract OCR を別途インストールする必要があります
     https://github.com/UB-Mannheim/tesseract/wiki
""".strip()


# ---------------------------------------------------------------------------
# メインアプリ
# ---------------------------------------------------------------------------

class PDFOCRApp:
    """PDF OCRツール メインウィンドウ。"""

    def __init__(self, root: tk.Tk):
        self.root    = root
        self.files:   list[Path]          = []
        self.results: list[ProcessResult] = []
        self._processing = False
        self._log_queue: queue.Queue = queue.Queue()

        # 設定
        self._config_path = TOOL_DIR / "config.json"
        self._config      = load_config(str(self._config_path))

        self._setup_window()
        self._setup_logging()
        self._apply_styles()
        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._bind_keys()
        self._poll_logs()
        self._set_status(
            "PDFを追加して [▶ 処理開始] を押してください。"
            "  Ctrl+O: ファイル追加  Ctrl+D: フォルダ  F5: 処理開始  Ctrl+S: 出力"
        )

    # ------------------------------------------------------------------ #
    #  初期化                                                              #
    # ------------------------------------------------------------------ #

    def _setup_window(self):
        self.root.title(f"{APP_TITLE}  v{APP_VERSION}")
        self.root.geometry(WIN_SIZE)
        self.root.minsize(*WIN_MIN)
        self.root.configure(bg=APP_BG)
        # 画面中央に配置
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        ww, wh = (int(x) for x in WIN_SIZE.split("x"))
        self.root.geometry(f"{ww}x{wh}+{(sw - ww)//2}+{(sh - wh)//2}")

    def _setup_logging(self):
        log_dir = TOOL_DIR / self._config.get("log_dir", "logs")
        log_dir.mkdir(exist_ok=True)

        handler = _QueueHandler(self._log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # 重複追加を防ぐ
        if not any(isinstance(h, _QueueHandler) for h in root_logger.handlers):
            root_logger.addHandler(handler)

        file_handler = logging.FileHandler(str(log_dir / "log.txt"), encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
            root_logger.addHandler(file_handler)

    def _apply_styles(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Accent.TButton",
                    font=("Yu Gothic UI", 10, "bold"), padding=(10, 6),
                    background=ACCENT_COLOR, foreground=ACCENT_FG)
        s.map("Accent.TButton",
              background=[("active", "#1a3a70"), ("disabled", "#9E9E9E")])
        s.configure("TButton", font=("Yu Gothic UI", 9), padding=(8, 5))
        s.configure("Header.TLabel",
                    background=ACCENT_COLOR, foreground=ACCENT_FG,
                    font=("Yu Gothic UI", 10, "bold"), padding=(8, 5))
        s.configure("Status.TLabel",
                    background="#E0E0E0", padding=(8, 4),
                    font=("Yu Gothic UI", 9))
        s.configure("Prog.TProgressbar", thickness=16, troughcolor="#E0E0E0",
                    background=ACCENT_COLOR)

    # ------------------------------------------------------------------ #
    #  メニュー                                                            #
    # ------------------------------------------------------------------ #

    def _build_menu(self):
        mb = tk.Menu(self.root)
        self.root.config(menu=mb)

        # ファイル
        fm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="ファイル", menu=fm)
        fm.add_command(label="PDFを追加…  Ctrl+O",    command=self._add_files)
        fm.add_command(label="フォルダを選択…  Ctrl+D", command=self._add_folder)
        fm.add_separator()
        fm.add_command(label="リストをクリア",          command=self._clear_files)
        fm.add_separator()
        fm.add_command(label="Excel出力…  Ctrl+S",    command=self._export_excel)
        fm.add_separator()
        fm.add_command(label="終了",                   command=self.root.quit)

        # 設定
        sm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="設定", menu=sm)
        sm.add_command(label="設定を編集…", command=self._open_settings)

        # ヘルプ
        hm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="ヘルプ", menu=hm)
        hm.add_command(label="使い方", command=self._show_help)
        hm.add_command(label=f"バージョン情報", command=lambda: messagebox.showinfo(
            "バージョン", f"{APP_TITLE}  v{APP_VERSION}\nPython {sys.version.split()[0]}"))

    # ------------------------------------------------------------------ #
    #  ツールバー                                                          #
    # ------------------------------------------------------------------ #

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(8, 5))
        bar.pack(fill=tk.X)

        ttk.Button(bar, text="📂 ファイル追加",  command=self._add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="📁 フォルダ選択",  command=self._add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="🗑 クリア",        command=self._clear_files).pack(side=tk.LEFT, padx=2)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)

        self._btn_process = ttk.Button(
            bar, text="▶ 処理開始  F5",
            style="Accent.TButton", command=self._start_processing)
        self._btn_process.pack(side=tk.LEFT, padx=2)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)

        self._btn_export = ttk.Button(
            bar, text="💾 Excel出力  Ctrl+S",
            command=self._export_excel, state=tk.DISABLED)
        self._btn_export.pack(side=tk.LEFT, padx=2)

        # 右端：進捗
        self._prog_label = ttk.Label(bar, text="")
        self._prog_label.pack(side=tk.RIGHT, padx=(4, 0))
        self._prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(
            bar, variable=self._prog_var, maximum=100,
            style="Prog.TProgressbar", length=180,
        ).pack(side=tk.RIGHT, padx=8)

    # ------------------------------------------------------------------ #
    #  メインボディ（左ペイン：ファイルリスト / 右ペイン：結果+ログ）      #
    # ------------------------------------------------------------------ #

    def _build_body(self):
        pw = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))

        # 左：ファイルリスト
        left = ttk.Frame(pw)
        pw.add(left, weight=1)
        self._build_file_panel(left)

        # 右：縦分割（上: 結果タブ / 下: ログ）
        rw = ttk.PanedWindow(pw, orient=tk.VERTICAL)
        pw.add(rw, weight=2)

        top_right = ttk.Frame(rw)
        rw.add(top_right, weight=3)
        self._build_result_tabs(top_right)

        bot_right = ttk.Frame(rw)
        rw.add(bot_right, weight=1)
        self._build_log_panel(bot_right)

    # ---- ファイルリスト ---- #

    def _build_file_panel(self, parent):
        ttk.Label(parent, text="  処理ファイル一覧", style="Header.TLabel").pack(fill=tk.X)

        cols = ("name", "type", "date", "amount", "status")
        self._ftree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="extended")

        col_defs = [
            ("name",   "ファイル名", 170, tk.W),
            ("type",   "種類",        56, tk.CENTER),
            ("date",   "日付",        96, tk.W),
            ("amount", "金額",        82, tk.E),
            ("status", "状態",        64, tk.CENTER),
        ]
        for cid, text, w, anchor in col_defs:
            self._ftree.heading(cid, text=text)
            self._ftree.column(cid, width=w, minwidth=40, anchor=anchor)

        for status, (fg, bg) in STATUS_STYLE.items():
            self._ftree.tag_configure(status, foreground=fg, background=bg)

        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL,   command=self._ftree.yview)
        hsb = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self._ftree.xview)
        self._ftree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._ftree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # ドロップターゲット
        if HAS_DND:
            self._ftree.drop_target_register(DND_FILES)
            self._ftree.dnd_bind("<<Drop>>", self._on_drop)
        else:
            ttk.Label(parent,
                      text="※ ドラッグ&ドロップは tkinterdnd2 で有効になります",
                      foreground="#9E9E9E", font=("Yu Gothic UI", 8)
                      ).pack(pady=2)

        # 右クリックメニュー
        self._ctx = tk.Menu(self.root, tearoff=0)
        self._ctx.add_command(label="選択ファイルを削除  Del", command=self._remove_selected)
        self._ctx.add_command(label="ファイルを開く",          command=self._open_selected)
        self._ftree.bind("<Button-3>", self._show_ctx)
        self._ftree.bind("<Delete>",   lambda _: self._remove_selected())

    # ---- 結果タブ ---- #

    def _build_result_tabs(self, parent):
        ttk.Label(parent, text="  抽出結果プレビュー", style="Header.TLabel").pack(fill=tk.X)

        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        hf = ttk.Frame(nb)
        nb.add(hf, text="  ヘッダ  ")
        self._htree = self._make_treeview(
            hf,
            cols=[("fname","ファイル名",155,tk.W),
                  ("type","種類",56,tk.CENTER),
                  ("date","日付",96,tk.W),
                  ("amount","金額",88,tk.E),
                  ("company","会社名",155,tk.W),
                  ("number","番号",110,tk.W)],
        )

        df = ttk.Frame(nb)
        nb.add(df, text="  明細  ")
        self._dtree = self._make_treeview(
            df,
            cols=[("fname","ファイル名",155,tk.W),
                  ("row","行",38,tk.E),
                  ("name","品名",195,tk.W),
                  ("qty","数量",58,tk.E),
                  ("unit","単価",88,tk.E),
                  ("amt","金額",88,tk.E)],
        )

    def _make_treeview(self, parent, cols: list) -> ttk.Treeview:
        """スクロールバー付き Treeview を生成して返す。"""
        tv = ttk.Treeview(parent, columns=[c[0] for c in cols], show="headings")
        for cid, text, w, anchor in cols:
            tv.heading(cid, text=text,
                       command=lambda c=cid, t=tv: self._sort_tree(t, c))
            tv.column(cid, width=w, minwidth=30, anchor=anchor)

        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL,   command=tv.yview)
        hsb = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=tv.xview)
        tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side=tk.RIGHT,  fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        tv.pack(fill=tk.BOTH, expand=True)
        return tv

    # ---- ログパネル ---- #

    def _build_log_panel(self, parent):
        ttk.Label(parent, text="  処理ログ", style="Header.TLabel").pack(fill=tk.X)

        self._log_widget = ScrolledText(
            parent, state=tk.DISABLED, height=7,
            font=("Consolas", 9),
            bg=LOG_BG, fg=LOG_FG, insertbackground=LOG_FG,
            relief=tk.FLAT,
        )
        self._log_widget.pack(fill=tk.BOTH, expand=True)
        self._log_widget.tag_configure("INFO",    foreground="#9CDCFE")
        self._log_widget.tag_configure("WARNING", foreground="#CE9178")
        self._log_widget.tag_configure("ERROR",   foreground="#F48771")

    # ------------------------------------------------------------------ #
    #  ステータスバー                                                      #
    # ------------------------------------------------------------------ #

    def _build_statusbar(self):
        self._status_var = tk.StringVar()
        ttk.Label(
            self.root, textvariable=self._status_var,
            style="Status.TLabel", anchor=tk.W,
        ).pack(fill=tk.X, side=tk.BOTTOM)

    # ------------------------------------------------------------------ #
    #  キーバインド                                                        #
    # ------------------------------------------------------------------ #

    def _bind_keys(self):
        self.root.bind("<Control-o>", lambda _: self._add_files())
        self.root.bind("<Control-d>", lambda _: self._add_folder())
        self.root.bind("<Control-s>", lambda _: self._export_excel())
        self.root.bind("<F5>",        lambda _: self._start_processing())

    # ------------------------------------------------------------------ #
    #  ファイル操作                                                        #
    # ------------------------------------------------------------------ #

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="PDFファイルを選択",
            filetypes=[("PDF", "*.pdf *.PDF"), ("すべて", "*.*")],
        )
        self._register_files([Path(p) for p in paths])

    def _add_folder(self):
        folder = filedialog.askdirectory(title="フォルダを選択")
        if folder:
            pdfs = sorted(Path(folder).glob("*.pdf")) + sorted(Path(folder).glob("*.PDF"))
            self._register_files(pdfs)

    def _register_files(self, paths: list[Path]):
        existing = {f.resolve() for f in self.files}
        added = 0
        for p in paths:
            if not p.is_file():
                continue
            if p.resolve() in existing:
                continue
            self.files.append(p)
            self._ftree.insert("", tk.END, iid=str(p),
                               values=(p.name, "", "", "", "待機"),
                               tags=("待機",))
            added += 1
        if added:
            self._set_status(f"{added}件追加（合計 {len(self.files)}件）")
        else:
            self._set_status("追加できるファイルがありませんでした（重複または存在しないファイル）")

    def _on_drop(self, event):
        paths = [Path(p) for p in self.root.tk.splitlist(event.data)
                 if p.lower().endswith(".pdf")]
        self._register_files(paths)

    def _remove_selected(self):
        selected = self._ftree.selection()
        for iid in selected:
            p = Path(iid)
            if p in self.files:
                self.files.remove(p)
            self._ftree.delete(iid)
        if selected:
            self._set_status(f"{len(selected)}件削除（残り {len(self.files)}件）")

    def _clear_files(self):
        if self._processing:
            messagebox.showwarning("処理中", "処理が完了してからクリアしてください。")
            return
        self.files.clear()
        self.results.clear()
        for tree in (self._ftree, self._htree, self._dtree):
            tree.delete(*tree.get_children())
        self._btn_export.config(state=tk.DISABLED)
        self._prog_var.set(0)
        self._prog_label.config(text="")
        self._set_status("リストをクリアしました。")

    def _open_selected(self):
        for iid in self._ftree.selection():
            _open_file(iid)

    def _show_ctx(self, event):
        row = self._ftree.identify_row(event.y)
        if row:
            self._ftree.selection_set(row)
            self._ctx.tk_popup(event.x_root, event.y_root)

    # ------------------------------------------------------------------ #
    #  処理                                                                #
    # ------------------------------------------------------------------ #

    def _start_processing(self):
        if self._processing:
            return
        if not self.files:
            messagebox.showinfo("ファイルなし", "処理するPDFを追加してください。")
            return

        self._processing = True
        self.results.clear()
        self._btn_process.config(state=tk.DISABLED)
        self._btn_export.config(state=tk.DISABLED)

        # 結果テーブルをクリア
        self._htree.delete(*self._htree.get_children())
        self._dtree.delete(*self._dtree.get_children())

        # 全ファイルを「待機」にリセット
        for p in self.files:
            iid = str(p)
            if self._ftree.exists(iid):
                self._ftree.item(iid, values=(p.name, "", "", "", "待機"), tags=("待機",))

        self._set_status(f"処理開始：{len(self.files)}件")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        """バックグラウンドワーカースレッド。"""
        logger = logging.getLogger(__name__)
        rules_dir    = str(TOOL_DIR / self._config.get("rules_dir", "rules"))
        ocr_language = self._config.get("ocr_language", "jpn+eng")
        ocr_dpi      = int(self._config.get("ocr_dpi", 300))
        total        = len(self.files)

        for i, pdf_path in enumerate(self.files):
            # 処理中に更新
            self.root.after(0, self._set_file_status, pdf_path, "処理中", "", "", "")

            result = process_single_pdf(pdf_path, rules_dir, ocr_language, ocr_dpi, logger)
            self.results.append(result)

            # UI更新はメインスレッドで
            self.root.after(0, self._on_result, result, i + 1, total)

        self.root.after(0, self._on_done)

    def _on_result(self, r: ProcessResult, current: int, total: int):
        """1ファイル完了時のUI更新（メインスレッド）。"""
        label = DOC_TYPE_LABELS.get(r.doc_type, r.doc_type)
        h     = r.header or {}

        status = {"success": "完了", "unknown": "不明", "error": "エラー"}.get(r.status, "完了")
        amount_str = _fmt_amount(h.get("amount"))
        date_str   = h.get("date") or ""

        self._set_file_status(r.pdf_path, status, label, date_str, amount_str)

        # ヘッダテーブル
        self._htree.insert("", tk.END, values=(
            r.pdf_path.name, label,
            date_str, amount_str,
            h.get("company") or "",
            h.get("number")  or "",
        ))

        # 明細テーブル
        for i, d in enumerate(r.details, 1):
            self._dtree.insert("", tk.END, values=(
                r.pdf_path.name, i,
                d.get("name")       or "",
                d.get("quantity")   or "",
                _fmt_amount(d.get("unit_price")),
                _fmt_amount(d.get("amount")),
            ))

        # 進捗
        pct = current / total * 100
        self._prog_var.set(pct)
        self._prog_label.config(text=f"{current} / {total}")
        self._set_status(f"処理中… {current}/{total}件  {r.pdf_path.name} → {status}")

    def _on_done(self):
        self._processing = False
        self._btn_process.config(state=tk.NORMAL)
        if self.results:
            self._btn_export.config(state=tk.NORMAL)

        success = sum(1 for r in self.results if r.status == "success")
        unknown = sum(1 for r in self.results if r.status == "unknown")
        error   = sum(1 for r in self.results if r.status == "error")
        details = sum(len(r.details) for r in self.results)

        summary = (f"処理完了  ✔ 成功:{success}件  "
                   f"⚠ 不明:{unknown}件  ✘ エラー:{error}件  "
                   f"明細:{details}行")
        self._set_status(summary)
        self._prog_var.set(100)
        logging.getLogger(__name__).info(summary)

    def _set_file_status(self, pdf_path: Path, status: str,
                          doc_type: str, date: str, amount: str):
        iid = str(pdf_path)
        if self._ftree.exists(iid):
            self._ftree.item(iid,
                             values=(pdf_path.name, doc_type, date, amount, status),
                             tags=(status,))

    # ------------------------------------------------------------------ #
    #  Excel出力                                                           #
    # ------------------------------------------------------------------ #

    def _export_excel(self):
        if not self.results:
            messagebox.showinfo("データなし", "先に処理を実行してください。")
            return

        out_dir = TOOL_DIR / self._config.get("output_dir", "output")
        out_dir.mkdir(exist_ok=True)

        save_path = filedialog.asksaveasfilename(
            title="Excel ファイルとして保存",
            initialdir=str(out_dir),
            initialfile=self._config.get("output_file", "result.xlsx"),
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("すべて", "*.*")],
        )
        if not save_path:
            return

        try:
            headers, details = results_to_excel_rows(self.results)
            write_excel(headers, details, save_path)
            self._set_status(f"Excel出力完了: {save_path}")
            logging.getLogger(__name__).info(f"Excel出力: {save_path}")

            if messagebox.askyesno("出力完了", f"保存しました。\n{save_path}\n\nファイルを開きますか？"):
                _open_file(save_path)

        except Exception as e:
            messagebox.showerror("出力エラー", f"Excel出力に失敗しました。\n{e}")
            logging.getLogger(__name__).error(f"Excel出力失敗: {e}", exc_info=True)

    # ------------------------------------------------------------------ #
    #  設定 / ヘルプ                                                       #
    # ------------------------------------------------------------------ #

    def _open_settings(self):
        SettingsDialog(self.root, self._config_path, self._config,
                       self._on_config_saved)

    def _on_config_saved(self, new_cfg: dict):
        self._config = new_cfg
        self._set_status("設定を保存しました。")

    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("使い方")
        win.geometry("520x440")
        win.transient(self.root)
        st = ScrolledText(win, wrap=tk.WORD, font=("Yu Gothic UI", 10),
                          padx=12, pady=12, relief=tk.FLAT)
        st.pack(fill=tk.BOTH, expand=True)
        st.insert("1.0", _HELP_TEXT)
        st.config(state=tk.DISABLED)
        ttk.Button(win, text="閉じる", command=win.destroy).pack(pady=8)

    # ------------------------------------------------------------------ #
    #  ソート                                                              #
    # ------------------------------------------------------------------ #

    def _sort_tree(self, tree: ttk.Treeview, col: str):
        items = [(tree.set(iid, col), iid) for iid in tree.get_children()]
        # 数値ならint変換でソート
        def key(x):
            v = x[0]
            if v == "":
                return (1, 0, "")
            try:
                return (0, int(str(v).replace(",", "").replace("¥", "")), "")
            except ValueError:
                return (0, 0, v)
        items.sort(key=key)
        for idx, (_, iid) in enumerate(items):
            tree.move(iid, "", idx)

    # ------------------------------------------------------------------ #
    #  ログポーリング                                                      #
    # ------------------------------------------------------------------ #

    def _poll_logs(self):
        try:
            while True:
                level, msg = self._log_queue.get_nowait()
                self._append_log(level, msg)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_logs)

    def _append_log(self, level: str, msg: str):
        w = self._log_widget
        w.config(state=tk.NORMAL)
        tag = level if level in ("WARNING", "ERROR") else "INFO"
        w.insert(tk.END, msg + "\n", tag)
        w.see(tk.END)
        w.config(state=tk.DISABLED)

    # ------------------------------------------------------------------ #
    #  ステータス                                                          #
    # ------------------------------------------------------------------ #

    def _set_status(self, msg: str):
        self._status_var.set(f"  {msg}")


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------

def main():
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    PDFOCRApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
