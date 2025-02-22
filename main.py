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
from modules.audio_splitter import AudioSplitter
from modules.transcriber import GeminiTranscriber
from modules.audio_processor import AudioProcessor


# ロガーの初期化
logger = logging.getLogger(__name__)

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

def setup_ffmpeg():
    """FFmpegの設定"""
    try:
        # 一時ディレクトリの作成
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
        # FFmpegの実行ファイルパス
        if getattr(sys, 'frozen', False):
            # PyInstallerでビルドされた場合
            ffmpeg_src = BASE_DIR / 'resources' / 'ffmpeg' / 'ffmpeg.exe'
            if not ffmpeg_src.exists():
                # バックアップパスとしてAPP_DIRも確認
                ffmpeg_src = APP_DIR / 'resources' / 'ffmpeg' / 'ffmpeg.exe'
            logging.debug(f"PyInstaller実行モード: FFmpegパス = {ffmpeg_src}")
        else:
            # 通常実行時
            ffmpeg_src = BASE_DIR / 'resources' / 'ffmpeg' / 'ffmpeg.exe'
            logging.debug(f"通常実行モード: FFmpegパス = {ffmpeg_src}")
        
        if not ffmpeg_src.exists():
            logging.error(f"FFmpeg実行ファイルが見つかりません: {ffmpeg_src}")
            logging.debug(f"現在のBASE_DIR: {BASE_DIR}")
            logging.debug(f"現在のAPP_DIR: {APP_DIR}")
            # 利用可能なパスを探索
            possible_paths = [
                BASE_DIR / 'resources' / 'ffmpeg' / 'ffmpeg.exe',
                APP_DIR / 'resources' / 'ffmpeg' / 'ffmpeg.exe',
                BASE_DIR / 'ffmpeg.exe',
                APP_DIR / 'ffmpeg.exe'
            ]
            for path in possible_paths:
                logging.debug(f"FFmpegを探索中: {path}")
                if path.exists():
                    ffmpeg_src = path
                    logging.info(f"FFmpegが見つかりました: {path}")
                    break
            else:
                raise FileNotFoundError(f"FFmpeg実行ファイルが見つかりません: {ffmpeg_src}")
            
        ffmpeg_dest = TEMP_DIR / 'ffmpeg.exe'
        logging.debug(f"FFmpeg一時ファイルパス: {ffmpeg_dest}")
        
        # FFmpegが一時ディレクトリに存在しない場合はコピー
        if not ffmpeg_dest.exists():
            shutil.copy2(ffmpeg_src, ffmpeg_dest)
            logging.debug("FFmpegファイルを一時ディレクトリにコピーしました")
            
        # 環境変数にFFmpegのパスを設定
        os.environ['FFMPEG_BINARY'] = str(ffmpeg_dest)
        
        logging.info(f"FFmpegを設定しました: {ffmpeg_dest}")
        
    except Exception as e:
        logging.error(f"FFmpegの設定中にエラーが発生しました: {e}")
        raise

def cleanup_temp():
    """一時ファイルのクリーンアップ"""
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
            logging.info("一時ファイルのクリーンアップが完了しました")
    except Exception as e:
        logging.error(f"一時ファイルの削除中にエラーが発生しました: {e}")

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
        with open('config/settings.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"設定ファイルの読み込み中にエラーが発生しました: {str(e)}")
        raise

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
            logger.info("既存の処理方式を使用します")
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
        logger.info("強制的に一時ファイルのクリーンアップを実行します...")
        cleanup_temp()
        logger.info(f"アプリケーションを起動中... (実行パス: {BASE_DIR})")
        logger.debug(f"実行パス: {BASE_DIR}")
        logger.debug(f"アプリケーションパス: {APP_DIR}")
        
        # FFmpegの設定
        logger.info("FFmpegの設定を開始します...")
        setup_ffmpeg()
        
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