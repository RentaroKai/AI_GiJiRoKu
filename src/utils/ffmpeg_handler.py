"""
FFMPEGハンドラーモジュール

FFMPEG関連の機能を一元化して管理するモジュール。
- バイナリの検出
- パスの解決
- 環境変数の設定
- pydubの設定

Date: 2023-03-07
"""

import os
import sys
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

def get_base_path():
    """
    実行環境に合わせたベースパスを返す。
    - PyInstallerでビルドされた実行環境の場合は sys._MEIPASS を返す
    - 通常の Python 実行の場合は、プロジェクトルートを返す
    """
    if getattr(sys, 'frozen', False):
        # PyInstallerによる実行環境
        base_path = sys._MEIPASS
        logger.debug(f"EXE実行モード: base_path = {base_path}")
    else:
        # 通常のPython実行環境
        base_path = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        logger.debug(f"Python実行モード: base_path = {base_path}")
    return base_path

def get_ffmpeg_path():
    """
    FFmpeg実行ファイルのパスを返す。
    複数の可能性のあるパスを順番に探索し、最初に見つかったパスを返す。
    """
    base_path = get_base_path()
    
    # 最初に探索する標準パス
    ffmpeg_path = os.path.join(base_path, "resources", "ffmpeg", "ffmpeg.exe")
    
    if os.path.exists(ffmpeg_path):
        logger.debug(f"FFmpegパスが見つかりました: {ffmpeg_path}")
        return ffmpeg_path
    
    # 標準パスに見つからない場合は、他の可能性のあるパスを探索
    logger.warning(f"標準パスにFFmpegが見つかりませんでした: {ffmpeg_path}")
    possible_paths = [
        os.path.join(base_path, "ffmpeg.exe"),  # ルートディレクトリ
        os.path.join(os.path.dirname(base_path), "resources", "ffmpeg", "ffmpeg.exe"),  # 親ディレクトリのリソース
        shutil.which("ffmpeg")  # システムパスに設定されているffmpeg
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            logger.info(f"代替のFFmpegパスが見つかりました: {path}")
            return path
    
    logger.error("FFmpegが見つかりませんでした")
    return None

def get_ffprobe_path():
    """
    ffprobe実行ファイルのパスを返す。
    複数の可能性のあるパスを順番に探索し、最初に見つかったパスを返す。
    """
    base_path = get_base_path()
    
    # 最初に探索する標準パス
    ffprobe_path = os.path.join(base_path, "resources", "ffmpeg", "ffprobe.exe")
    
    if os.path.exists(ffprobe_path):
        logger.debug(f"ffprobeパスが見つかりました: {ffprobe_path}")
        return ffprobe_path
    
    # 標準パスに見つからない場合は、他の可能性のあるパスを探索
    logger.warning(f"標準パスにffprobeが見つかりませんでした: {ffprobe_path}")
    possible_paths = [
        os.path.join(base_path, "ffprobe.exe"),  # ルートディレクトリ
        os.path.join(os.path.dirname(base_path), "resources", "ffmpeg", "ffprobe.exe"),  # 親ディレクトリのリソース
        shutil.which("ffprobe")  # システムパスに設定されているffprobe
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            logger.info(f"代替のffprobeパスが見つかりました: {path}")
            return path
    
    logger.error("ffprobeが見つかりませんでした")
    return None

def setup_ffmpeg():
    """
    FFmpegの環境設定を行う。
    - FFmpegとffprobeのパスを取得
    - 環境変数を設定（PATH, FFMPEG_BINARY, FFPROBE_BINARY）
    - pydubの設定を更新

    Returns:
        tuple: (ffmpeg_path, ffprobe_path) - 設定されたパス
    """
    try:
        # FFmpegのパスを取得
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            raise FileNotFoundError("FFmpegが見つかりませんでした。アプリケーションが正常に動作しない可能性があります。")
        
        # ffprobeのパスを取得
        ffprobe_path = get_ffprobe_path()
        
        # FFmpegのディレクトリをPATHに追加
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        logger.debug(f"PATHを更新しました: {ffmpeg_dir} を追加")
        
        # pydubのconverter設定
        try:
            from pydub import AudioSegment
            AudioSegment.converter = ffmpeg_path
            if ffprobe_path:
                AudioSegment.ffprobe = ffprobe_path
            logger.debug(f"pydub設定を更新しました: converter={ffmpeg_path}, ffprobe={ffprobe_path}")
        except ImportError:
            logger.warning("pydubのインポートに失敗しました。AudioSegment設定はスキップします。")
        
        # 環境変数の設定
        os.environ["FFMPEG_BINARY"] = ffmpeg_path
        if ffprobe_path:
            os.environ["FFPROBE_BINARY"] = ffprobe_path
        
        logger.info(f"FFmpeg設定が完了しました: ffmpeg={ffmpeg_path}, ffprobe={ffprobe_path}")
        return ffmpeg_path, ffprobe_path
        
    except Exception as e:
        logger.error(f"FFmpeg設定中にエラーが発生しました: {str(e)}", exc_info=True)
        raise 