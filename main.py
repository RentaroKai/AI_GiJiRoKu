import os
import sys
import tkinter as tk
from tkinter import messagebox
import logging
import shutil
import atexit
import json
from pathlib import Path

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

def setup_config():
    """設定ファイルの初期化（存在する場合は初期化しない）"""
    try:
        # transcription_config.jsonの初期化（存在しない場合のみ）
        config_dir = Path("config")
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # デフォルトの出力ディレクトリを設定
        default_output_dir = setup_default_output_dir()
        
        transcription_config_path = config_dir / "transcription_config.json"
        if not transcription_config_path.exists():
            logging.info("書き起こし設定ファイルが存在しないため、新規作成します")
            default_transcription_config = {
                "transcription": {
                    "method": "whisper_gpt4"  # デフォルトをWhisper + GPT-4方式に設定
                },
                "output": {
                    "default_dir": str(default_output_dir)  # デフォルトの出力ディレクトリを設定
                }
            }
            with open(transcription_config_path, "w", encoding="utf-8") as f:
                json.dump(default_transcription_config, f, indent=2, ensure_ascii=False)
            logging.info("書き起こし設定ファイルを作成しました")
        else:
            # 既存の設定ファイルにデフォルトの出力ディレクトリ設定を追加
            with open(transcription_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            if "output" not in config:
                config["output"] = {"default_dir": str(default_output_dir)}
                with open(transcription_config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                logging.info("既存の設定ファイルにデフォルトの出力ディレクトリ設定を追加しました")
            
            logging.info("既存の書き起こし設定ファイルを使用します")
    except Exception as e:
        logging.error(f"設定ファイルの初期化中にエラーが発生しました: {e}")
        raise

def main():
    """アプリケーションのメインエントリーポイント"""
    try:
        # ロギングの設定
        print("ロギングの設定を開始します...")
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info(f"アプリケーションを起動中... (実行パス: {BASE_DIR})")
        print(f"実行パス: {BASE_DIR}")
        print(f"アプリケーションパス: {APP_DIR}")
        
        # 設定ファイルの初期化
        print("設定ファイルを初期化します...")
        setup_config()
        
        # FFmpegの設定
        print("FFmpegの設定を開始します...")
        setup_ffmpeg()
        
        # 終了時の一時ファイルクリーンアップを登録
        atexit.register(cleanup_temp)
        
        # 必要なディレクトリの作成
        print("必要なディレクトリを作成します...")
        for dir_path in ["output/transcriptions", "output/csv", "output/minutes", "logs"]:
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                print(f"ディレクトリを作成しました: {dir_path}")
            except Exception as e:
                print(f"ディレクトリの作成に失敗しました: {dir_path} - {str(e)}")
        
        # メインウィンドウの作成
        print("メインウィンドウを作成します...")
        root = tk.Tk()
        app = MainWindow(root)
        
        # アプリケーションの実行
        logger.info("メインイベントループを開始します")
        print("アプリケーションを開始します...")
        root.mainloop()
        
    except Exception as e:
        error_msg = f"致命的なエラーが発生しました: {str(e)}"
        print(error_msg)
        if 'logger' in locals():
            logger.error(error_msg)
        # エラーダイアログを表示
        tk.messagebox.showerror("エラー", error_msg)
        raise

if __name__ == "__main__":
    main() 