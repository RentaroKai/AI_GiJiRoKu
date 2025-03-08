"""
パス解決ユーティリティ

Changes:
- ffmpeg_handler モジュールを使用するように更新
- 既存の関数はそのままに、内部実装を変更
"""

import os
import sys
from src.utils.ffmpeg_handler import get_base_path as handler_get_base_path
from src.utils.ffmpeg_handler import get_ffmpeg_path as handler_get_ffmpeg_path
from src.utils.ffmpeg_handler import get_ffprobe_path as handler_get_ffprobe_path

def get_base_path():
    """
    実行環境に合わせたベースパスを返す。
    - PyInstallerでビルドされた実行環境の場合は sys._MEIPASS を返す
    - 通常の Python 実行の場合は、プロジェクトルートを返す
    """
    return handler_get_base_path()

def get_ffmpeg_path():
    """
    FFmpeg実行ファイルの絶対パスを返す。
    """
    return handler_get_ffmpeg_path()

def get_ffprobe_path():
    """
    ffprobe実行ファイルの絶対パスを返す。
    """
    return handler_get_ffprobe_path() 