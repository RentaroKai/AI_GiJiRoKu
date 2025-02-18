import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import pathlib
import threading
import subprocess
import os
from typing import Optional
from ..services.audio import AudioProcessor, AudioProcessingError
from ..services.transcription import TranscriptionService, TranscriptionError
from ..services.csv_converter import CSVConverterService, CSVConversionError
from ..services.file_organizer import FileOrganizer
from ..utils.config import config_manager, ConfigError
from ..services.processor import process_audio_file

logger = logging.getLogger(__name__)

class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("GiJiRoKu - 音声文字起こしツール")
        self.root.geometry("600x400")
        
        # サービスの初期化
        self.audio_processor = None  # 遅延初期化
        self.transcription_service = None  # 遅延初期化
        self.csv_converter = None  # 遅延初期化
        self.file_organizer = FileOrganizer(debug_mode=config_manager.get_config().debug_mode)
        
        self._create_widgets()
        self._setup_layout()

    def _create_widgets(self):
        """ウィジェットの作成"""
        # ファイル選択部分
        self.file_frame = ttk.LabelFrame(self.root, text="入力ファイル", padding=10)
        self.file_path_var = tk.StringVar()
        self.file_path_entry = ttk.Entry(self.file_frame, textvariable=self.file_path_var, width=50)
        self.browse_button = ttk.Button(self.file_frame, text="参照", command=self._browse_file)
        
        # モード選択部分
        self.mode_frame = ttk.LabelFrame(self.root, text="処理モード", padding=10)
        self.transcribe_var = tk.BooleanVar(value=True)
        self.minutes_var = tk.BooleanVar(value=True)
        self.reflection_var = tk.BooleanVar(value=False)
        
        self.transcribe_check = ttk.Checkbutton(
            self.mode_frame, 
            text="書き起こし", 
            variable=self.transcribe_var,
            state="disabled"  # 常に選択状態
        )
        self.minutes_check = ttk.Checkbutton(
            self.mode_frame,
            text="議事録",
            variable=self.minutes_var
        )
        self.reflection_check = ttk.Checkbutton(
            self.mode_frame,
            text="会議の反省点",
            variable=self.reflection_var
        )
        
        # ボタン部分
        self.open_output_button = ttk.Button(
            self.root,
            text="📁",
            command=self._open_output_dir
        )
        
        # 実行ボタン
        self.execute_button = ttk.Button(
            self.root,
            text="実行",
            command=self._execute_processing
        )
        
        # 設定ボタン
        self.settings_button = ttk.Button(
            self.root,
            text="設定",
            command=self._show_settings
        )
        
        # ステータス表示
        self.status_var = tk.StringVar(value="待機中")
        self.status_label = ttk.Label(self.root, textvariable=self.status_var)

    def _setup_layout(self):
        """レイアウトの設定"""
        # ファイル選択部分
        self.file_frame.pack(fill=tk.X, padx=10, pady=5)
        self.file_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.browse_button.pack(side=tk.LEFT)
        
        # モード選択部分
        self.mode_frame.pack(fill=tk.X, padx=10, pady=5)
        self.transcribe_check.pack(side=tk.LEFT, padx=5)
        self.minutes_check.pack(side=tk.LEFT, padx=5)
        self.reflection_check.pack(side=tk.LEFT, padx=5)
        
        # ボタン部分
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        self.execute_button.pack(side=tk.RIGHT, padx=5)
        self.settings_button.pack(side=tk.RIGHT, padx=5)
        self.open_output_button.pack(side=tk.RIGHT, padx=5)
        
        # ステータス表示
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

    def _browse_file(self):
        """ファイル選択ダイアログを表示"""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("音声/動画ファイル", "*.mp3 *.wav *.mp4 *.m4a *.aac *.flac *.ogg *.mkv *.avi *.mov *.flv"),
                ("音声ファイル", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg"),
                ("動画ファイル", "*.mp4 *.mkv *.avi *.mov *.flv"),
                ("すべてのファイル", "*.*")
            ]
        )
        if file_path:
            self.file_path_var.set(file_path)
            # ファイル形式に応じたステータス表示
            _, ext = os.path.splitext(file_path)
            ext = ext.lower().lstrip('.')
            if ext in ['m4a', 'aac', 'flac', 'ogg', 'mkv', 'avi', 'mov', 'flv']:
                self.status_var.set("注意: このファイル形式は変換が必要です。処理時間が長くなる可能性があります。")
            else:
                self.status_var.set("待機中")

    def _execute_processing(self):
        """処理の実行"""
        if not self.file_path_var.get():
            messagebox.showerror("エラー", "ファイルを選択してください。")
            return
        
        # UIの更新
        self.execute_button.state(["disabled"])
        self.status_var.set("処理中...")
        
        # 処理の実行（別スレッド）
        thread = threading.Thread(target=self._process_file)
        thread.start()

    def _process_file(self):
        """ファイル処理の実行（別スレッド）"""
        try:
            input_file = pathlib.Path(self.file_path_var.get())
            
            # 処理モードの設定
            modes = {
                "transcribe": self.transcribe_var.get(),
                "minutes": self.minutes_var.get(),
                "reflection": self.reflection_var.get()
            }
            
            # 処理の実行
            self.status_var.set("処理中...")
            results = process_audio_file(input_file, modes)
            
            # デバッグ用ログ出力
            logger.debug(f"処理結果: {results}")
            
            # ファイル整理の実行
            if results.get('transcription'):
                logger.debug(f"transcription結果: {results['transcription']}")
                timestamp = results['transcription'].get('timestamp')
                logger.debug(f"取得したtimestamp: {timestamp}")
                if timestamp:
                    try:
                        new_folder = self.file_organizer.organize_meeting_files(timestamp)
                        logger.info(f"ファイルを整理しました: {new_folder}")
                    except Exception as e:
                        logger.error(f"ファイル整理中にエラーが発生: {str(e)}")
                        # ファイル整理のエラーは主処理の完了通知には影響させない
            
            # 成功メッセージ
            self.root.after(0, lambda: messagebox.showinfo(
                "完了",
                f"処理が完了しました。\n\n"
                f"書き起こし: {results.get('transcription', {}).get('formatted_file', '未実行')}\n"
                f"CSV: {results.get('csv', '未実行')}\n"
                f"議事録: {results.get('minutes', '未実行')}\n"
                f"反省点: {results.get('reflection', '未実行')}"
            ))
            
        except (AudioProcessingError, TranscriptionError, CSVConversionError, ConfigError) as e:
            error_msg = str(e)
            if "FFmpeg" in error_msg:
                error_msg += "\n\n未対応の形式のファイルを変換中にエラーが発生しました。"
            self.root.after(0, lambda: messagebox.showerror("エラー", error_msg))
        except Exception as e:
            logger.error(f"予期せぬエラー: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("エラー", f"予期せぬエラーが発生しました: {str(e)}"))
        finally:
            # UI状態の復帰
            self.root.after(0, lambda: self.execute_button.state(["!disabled"]))
            self.root.after(0, lambda: self.status_var.set("待機中"))

    def _show_settings(self):
        """設定ダイアログの表示"""
        SettingsDialog(self.root)

    def _open_output_dir(self):
        """出力ディレクトリをエクスプローラーで開く"""
        try:
            output_dir = pathlib.Path("output").absolute()
            if not output_dir.exists():
                output_dir.mkdir(parents=True)
            os.startfile(str(output_dir))
        except Exception as e:
            logger.error(f"出力ディレクトリを開く際にエラーが発生しました: {str(e)}")
            messagebox.showerror("エラー", f"出力ディレクトリを開けませんでした: {str(e)}")

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("設定")
        self.geometry("400x300")
        self.transient(parent)
        self.grab_set()
        
        self.config = config_manager.get_config()
        self._create_widgets()
        self._setup_layout()

    def _create_widgets(self):
        """設定ダイアログのウィジェット作成"""
        # API Key設定
        self.api_key_var = tk.StringVar(value=self.config.openai_api_key or "")
        self.api_key_frame = ttk.LabelFrame(self, text="OpenAI API Key", padding=5)
        self.api_key_entry = ttk.Entry(self.api_key_frame, textvariable=self.api_key_var, show="*")
        
        # 出力ディレクトリ設定
        self.output_dir_var = tk.StringVar(value=self.config.output_base_dir)
        self.output_dir_frame = ttk.LabelFrame(self, text="出力ディレクトリ（今は動かないよ）", padding=5)
        self.output_dir_entry = ttk.Entry(self.output_dir_frame, textvariable=self.output_dir_var, state="readonly")
        self.output_dir_button = ttk.Button(
            self.output_dir_frame,
            text="参照",
            command=self._browse_output_dir,
            state="disabled"
        )
        
        # デバッグモード設定
        self.debug_var = tk.BooleanVar(value=self.config.debug_mode)
        self.debug_check = ttk.Checkbutton(
            self,
            text="デバッグモード",
            variable=self.debug_var
        )
        
        # 保存ボタン
        self.save_button = ttk.Button(
            self,
            text="保存",
            command=self._save_settings
        )
        
        # キャンセルボタン
        self.cancel_button = ttk.Button(
            self,
            text="キャンセル",
            command=self.destroy
        )

    def _setup_layout(self):
        """設定ダイアログのレイアウト設定"""
        # API Key設定
        self.api_key_frame.pack(fill=tk.X, padx=10, pady=5)
        self.api_key_entry.pack(fill=tk.X, padx=5)
        
        # 出力ディレクトリ設定
        self.output_dir_frame.pack(fill=tk.X, padx=10, pady=5)
        self.output_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.output_dir_button.pack(side=tk.LEFT, padx=5)
        
        # デバッグモード設定
        self.debug_check.pack(padx=10, pady=5)
        
        # ボタン
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        self.save_button.pack(side=tk.RIGHT, padx=5)
        self.cancel_button.pack(side=tk.RIGHT, padx=5)

    def _browse_output_dir(self):
        """出力ディレクトリ選択ダイアログ"""
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_dir_var.set(dir_path)

    def _save_settings(self):
        """設定の保存"""
        try:
            config_manager.update_config(
                openai_api_key=self.api_key_var.get(),
                output_base_dir=self.output_dir_var.get(),
                debug_mode=self.debug_var.get()
            )
            self.destroy()
        except ConfigError as e:
            messagebox.showerror("エラー", f"設定の保存に失敗しました: {str(e)}") 