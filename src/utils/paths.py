import os
import sys

def get_base_path():
    """
    実行環境に合わせたベースパスを返す。
    - PyInstallerでビルドされた実行環境の場合は sys._MEIPASS を返す
    - 通常の Python 実行の場合は、プロジェクトルートを返す
    """
    if getattr(sys, 'frozen', False):
        # frozen の場合は PyInstaller による実行環境
        return sys._MEIPASS
    else:
        # このファイル (src/utils/paths.py) の2階層上をプロジェクトルートとする
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def get_ffmpeg_path():
    """
    FFmpeg実行ファイルの絶対パスを返す。
    """
    base_path = get_base_path()
    return os.path.join(base_path, "resources", "ffmpeg", "ffmpeg.exe")

# 必要に応じて、ffprobe も同様に取得できる関数を追加可能
def get_ffprobe_path():
    """
    ffprobe実行ファイルの絶対パスを返す。
    ※最小構成のため、本来は必要なければこの関数は使用しない。
    """
    base_path = get_base_path()
    return os.path.join(base_path, "resources", "ffmpeg", "ffprobe.exe") 