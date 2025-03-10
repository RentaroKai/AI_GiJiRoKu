"""
Changes:
- FFMPEGの設定処理を一元化し、ffmpeg_handlerモジュールを使用するように変更
- 重複するパス解決とFFMPEG設定関数を削除
- 一時ファイル処理をシンプル化
- 明示的なFFMPEG設定処理を追加
Date: 2023-03-07
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox
import logging
import shutil
import atexit
import json
from pathlib import Path
from datetime import datetime
from src.modules.audio_processor import AudioProcessor
from pydub import AudioSegment
from src.utils.ffmpeg_handler import setup_ffmpeg
from src.utils.path_resolver import get_config_file_path

# ロガーの初期化
logger = logging.getLogger(__name__)

# ログ出力を設定します（デバッグ用）
logging.basicConfig(level=logging.DEBUG)

# FFMPEGの初期設定
ffmpeg_path, ffprobe_path = setup_ffmpeg()
logger.info(f"FFmpeg設定: {ffmpeg_path}, ffprobe: {ffprobe_path}")

# アプリケーションのベースディレクトリを設定
if getattr(sys, 'frozen', False):
    # PyInstallerで実行時のパス
    BASE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(sys.executable).parent  # 実行ファイルのディレクトリ
else:
    # 通常実行時のパス
    BASE_DIR = Path(__file__).parent
    APP_DIR = BASE_DIR

# 一時ディレクトリの設定
TEMP_DIR = Path(os.getenv('TEMP', os.getenv('TMP', '.'))) / 'GiJiRoKu'

def cleanup_temp():
    """一時ファイルおよびoutputフォルダー内のmp3とjsonファイルのクリーンアップを行う"""
    # 一時ファイルのクリーンアップ
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
            logging.info("一時ファイルのクリーンアップが完了しました")
    except Exception as e:
        logging.error(f"一時ファイルの削除中にエラーが発生しました: {e}")
        print(f"一時ファイルの削除中にエラーが発生しました: {e}")

    # outputフォルダー内のmp3とjsonファイルの削除
    try:
        output_folder = Path("output")
        if output_folder.exists():
            for file in output_folder.rglob("*"):
                if file.is_file() and file.suffix.lower() in [".mp3", ".json"]:
                    try:
                        file.unlink()
                        logging.info(f"削除しました: {file}")
                        print(f"削除しました: {file}")
                    except Exception as ex:
                        logging.error(f"{file} の削除に失敗: {ex}")
                        print(f"{file} の削除に失敗: {ex}")
        else:
            logging.info("outputフォルダーが存在しません。")
            print("outputフォルダーが存在しません。")
    except Exception as e:
        logging.error(f"outputフォルダー内のファイル削除中にエラー: {e}")
        print(f"outputフォルダー内のファイル削除中にエラー: {e}")

    # output/transcriptions/segments の削除
    try:
        segments_folder = Path("output/transcriptions/segments")
        if segments_folder.exists() and segments_folder.is_dir():
            shutil.rmtree(segments_folder)
            logging.info(f"削除しました: {segments_folder}")
            print(f"削除しました: {segments_folder}")
        else:
            logging.info(f"{segments_folder} は存在しません。")
            print(f"{segments_folder} は存在しません。")
    except Exception as ex:
        logging.error(f"{segments_folder} の削除に失敗: {ex}")
        print(f"{segments_folder} の削除に失敗: {ex}")

    # srcディレクトリをPythonパスに追加
    sys.path.insert(0, str(BASE_DIR))

from src.ui.main_window import MainWindow
from src.utils.config import config_manager

def setup_logging():
    """ロギングの初期設定"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    config = config_manager.get_config()
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

def setup_default_output_dir():
    """デフォルトの出力ディレクトリ（マイドキュメント/議事録）の初期設定"""
    try:
        # マイドキュメントのパスを取得
        documents_path = os.path.expanduser("~/Documents")
        # 議事録フォルダのパスを設定
        minutes_dir = os.path.join(documents_path, "議事録")
        
        # 議事録フォルダが存在しない場合は作成
        if not os.path.exists(minutes_dir):
            os.makedirs(minutes_dir)
            logging.info(f"デフォルトの出力ディレクトリを作成しました: {minutes_dir}")
            print(f"デフォルトの出力ディレクトリを作成しました: {minutes_dir}")
        else:
            logging.info(f"既存の出力ディレクトリを使用します: {minutes_dir}")
            print(f"既存の出力ディレクトリを使用します: {minutes_dir}")
            
        return minutes_dir
    except Exception as e:
        error_msg = f"デフォルトの出力ディレクトリの設定中にエラーが発生しました: {e}"
        logging.error(error_msg)
        print(error_msg)
        raise

def load_config():
    """設定ファイルを読み込む"""
    try:
        # 統一されたパス解決ユーティリティを使用
        config_file = get_config_file_path()
        logger.info(f"設定ファイルを読み込みます: {config_file.absolute()}")
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 設定内容のログ
                transcription_method = config.get('transcription', {}).get('method', 'gpt4_audio')
                logger.info(f"読み込まれた文字起こし方式: {transcription_method}")
                return config
        else:
            logger.warning(f"設定ファイルが見つかりません: {config_file}")
            return {}
    except Exception as e:
        logger.error(f"設定ファイルの読み込み中にエラーが発生しました: {str(e)}")
        return {}

def process_audio_file(input_file, config):
    """音声ファイルを処理する"""
    try:
        # 出力ディレクトリの設定
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join("output", timestamp)
        logger.info(f"出力ディレクトリを設定: {output_dir}")
        
        # 文字起こし方式に応じて処理を分岐
        transcription_method = config.get('transcription', {}).get('method', 'whisper_gpt4')
        logger.info(f"文字起こし方式: {transcription_method}")
        # 設定内容の詳細をログ出力
        logger.info(f"設定内容のダンプ: {json.dumps(config, ensure_ascii=False, indent=2)}")
        
        if transcription_method == "gemini":
            # Geminiを使用する場合はAudioProcessorを使用
            logger.info("Gemini APIを使用した処理を開始します")
            processor = AudioProcessor()
            output_file = processor.process_audio_file(
                input_file=input_file,
                output_dir=output_dir,
                segment_length_seconds=config['transcription'].get('segment_length_seconds', 600)
            )
        else:
            # 既存の処理（Whisper + GPT-4など）
            logger.info(f"既存の処理方式を使用します (方式: {transcription_method})")
            from src.services.processor import process_audio_file
            output_file = process_audio_file(input_file, {"transcribe": True})
        
        logger.info(f"文字起こしが完了しました。結果は {output_file} に保存されました")
        return output_file
        
    except Exception as e:
        logger.error(f"音声ファイルの処理中にエラーが発生しました: {str(e)}", exc_info=True)
        raise

def main():
    """アプリケーションのメインエントリーポイント"""
    try:
        # ロギングの設定
        print("ロギングの設定を開始します...")
        setup_logging()
        
        # 実行環境の情報をログに記録
        is_frozen = getattr(sys, 'frozen', False)
        logger.info(f"アプリケーション開始: 実行モード={'PyInstaller' if is_frozen else '通常'}")
        if is_frozen:
            logger.info(f"PyInstaller実行パス: {sys._MEIPASS}")
            logger.info(f"実行ファイルパス: {sys.executable}")
            
        logger.info("強制的に一時ファイルのクリーンアップを実行します...")
        cleanup_temp()
        
        logger.info(f"アプリケーションを起動中... (実行パス: {BASE_DIR})")
        logger.debug(f"実行パス: {BASE_DIR}")
        logger.debug(f"アプリケーションパス: {APP_DIR}")
                
        # 終了時の一時ファイルクリーンアップを登録
        atexit.register(cleanup_temp)
        
        # 必要なディレクトリの作成
        logger.info("必要なディレクトリを作成します...")
        for dir_path in ["output/transcriptions", "output/csv", "output/minutes", "logs"]:
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                logger.debug(f"ディレクトリを作成しました: {dir_path}")
            except Exception as e:
                logger.error(f"ディレクトリの作成に失敗しました: {dir_path} - {str(e)}")
        
        # メインウィンドウの作成
        logger.info("メインウィンドウを作成します...")
        root = tk.Tk()
        app = MainWindow(root)
        
        # アプリケーションの実行
        logger.info("メインイベントループを開始します")
        root.mainloop()
        
    except Exception as e:
        error_msg = f"致命的なエラーが発生しました: {str(e)}"
        logger.critical(error_msg, exc_info=True)
        # エラーダイアログを表示
        tk.messagebox.showerror("エラー", error_msg)
        raise

if __name__ == "__main__":
    main() 