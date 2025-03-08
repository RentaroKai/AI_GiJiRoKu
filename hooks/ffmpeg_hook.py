"""
FFmpeg実行ファイルのパスを設定するためのPyInstallerランタイムフック

Changes:
- 新しいffmpeg_handlerモジュールを使用するように更新
- シンプルな実装に変更
"""

import sys
import os
from pathlib import Path

# PyInstallerで実行されている場合のみ処理を行う
if hasattr(sys, '_MEIPASS'):
    try:
        # sys.pathにsrcディレクトリを追加してインポートできるようにする
        # この処理はエラーハンドリングに含める（sys._MEIPASSが存在してもsrcが存在しない可能性がある）
        src_path = os.path.join(sys._MEIPASS, 'src')
        if os.path.exists(src_path):
            sys.path.insert(0, src_path)
        
        # FFmpegハンドラーをインポートしてセットアップ
        try:
            from src.utils.ffmpeg_handler import setup_ffmpeg
            ffmpeg_path, ffprobe_path = setup_ffmpeg()
            print(f"FFmpeg設定完了: {ffmpeg_path}")
        except ImportError:
            # インポートに失敗した場合は、基本的なパス設定のみ行う
            ffmpeg_path = Path(sys._MEIPASS) / "resources" / "ffmpeg" / "ffmpeg.exe"
            ffprobe_path = Path(sys._MEIPASS) / "resources" / "ffmpeg" / "ffprobe.exe"
            
            if ffmpeg_path.exists():
                os.environ["FFMPEG_BINARY"] = str(ffmpeg_path)
                print(f"基本設定: FFMPEG_BINARY = {ffmpeg_path}")
            else:
                print(f"警告: FFmpeg実行ファイルが見つかりません: {ffmpeg_path}")
                
            if ffprobe_path.exists():
                os.environ["FFPROBE_BINARY"] = str(ffprobe_path)
                print(f"基本設定: FFPROBE_BINARY = {ffprobe_path}")
                
    except Exception as e:
        print(f"FFmpegフックの実行中にエラーが発生しました: {e}")