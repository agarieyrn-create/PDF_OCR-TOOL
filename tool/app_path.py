"""
app_path.py
通常の Python 実行と PyInstaller でビルドした exe の両方で
アプリケーションルートディレクトリを正しく返すヘルパー。

使い方:
    from app_path import APP_DIR
    config_path = APP_DIR / "config.json"
"""
import sys
from pathlib import Path


def get_app_dir() -> Path:
    """
    アプリのルートディレクトリを返す。

    - 通常実行時  : このファイルがある tool/ フォルダ
    - PyInstaller : .exe と同じフォルダ（ユーザーが解凍した場所）
    """
    if getattr(sys, "frozen", False):
        # PyInstaller でビルドされた exe として動作中
        return Path(sys.executable).parent
    # 通常の Python スクリプトとして動作中
    return Path(__file__).parent


APP_DIR: Path = get_app_dir()
