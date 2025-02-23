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
import json

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
        # スタイルの設定
        style = ttk.Style()
        style.configure(
            "Execute.TButton",
            background="#2F4F4F",  # ダークモスグリーン
            foreground="white"     # 白色
        )
        
        # ファイル選択部分
        self.file_frame = ttk.LabelFrame(self.root, text="入力ファイル", padding=10)
        self.file_path_var = tk.StringVar()
        self.file_path_entry = ttk.Entry(self.file_frame, textvariable=self.file_path_var, width=50)
        self.browse_button = ttk.Button(self.file_frame, text="ファイル選択", command=self._browse_file)
        
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
        self.open_output_button = tk.Button(
            self.root,
            text="📁",
            command=self._open_output_dir,
            relief="raised",
            padx=10,
            pady=5
        )
        
        # 実行ボタン
        self.execute_button = tk.Button(
            self.root,
            text="実行",
            command=self._execute_processing,
            bg="#2F4F4F",  # ダークモスグリーン
            fg="white",    # 白色
            relief="raised",
            padx=10,
            pady=5
        )
        
        # 設定ボタン
        self.settings_button = tk.Button(
            self.root,
            text="設定",
            command=self._show_settings,
            relief="raised",
            padx=10,
            pady=5
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

    def _animate_status_label(self):
        """ステータスラベルにアニメーションを表示する"""
        base_text = "処理中"
        current_text = self.status_var.get()
        if current_text.startswith(base_text):
            if current_text == base_text:
                new_text = base_text + "."
            elif current_text == base_text + ".":
                new_text = base_text + ".."
            elif current_text == base_text + "..":
                new_text = base_text + "..."
            else:
                new_text = base_text
            self.status_var.set(new_text)
            if self.status_var.get().startswith(base_text):
                self.root.after(500, self._animate_status_label)

    def _execute_processing(self):
        """処理の実行"""
        if not self.file_path_var.get():
            messagebox.showerror("エラー", "ファイルを選択してください。")
            return
        
        # UIの更新
        self.execute_button.config(state="disabled")
        self.status_var.set("処理中...")
        self._animate_status_label()
        
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
            self.root.after(0, lambda: self.execute_button.config(state="normal"))
            self.root.after(0, lambda: self.status_var.set("待機中"))

    def _show_settings(self):
        """設定ダイアログの表示"""
        SettingsDialog(self.root)

    def _open_output_dir(self):
        """出力ディレクトリをエクスプローラーで開く"""
        try:
            # 設定から出力ディレクトリを取得
            output_dir = self.file_organizer.get_output_directory()
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"出力ディレクトリを作成しました: {output_dir}")
            os.startfile(str(output_dir))
        except Exception as e:
            logger.error(f"出力ディレクトリを開く際にエラーが発生しました: {str(e)}")
            messagebox.showerror("エラー", f"出力ディレクトリを開けませんでした: {str(e)}")

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("設定")
        self.geometry("400x500")  # 高さを500に増やす
        self.transient(parent)
        self.grab_set()
        
        self.config = config_manager.get_config()
        # 設定値の取得（dictの場合とオブジェクトの場合の両方に対応）
        if isinstance(self.config, dict):
            self.transcription_method = self.config.get("transcription", {}).get("method", "whisper_gpt4")
            self.segment_length = self.config.get("transcription", {}).get("segment_length_seconds", 300)
            self.openai_api_key = self.config.get("openai_api_key", "")
            self.gemini_api_key = self.config.get("gemini_api_key", "")
            self.debug_mode = self.config.get("debug_mode", False)
            self.output_dir = self.config.get("output", {}).get("default_dir", "output")
        else:
            self.transcription_method = self.config.transcription.method
            self.segment_length = self.config.transcription.segment_length_seconds
            self.openai_api_key = self.config.openai_api_key or ""
            self.gemini_api_key = self.config.gemini_api_key or ""
            self.debug_mode = self.config.debug_mode
            self.output_dir = self.config.output.default_dir
        
        self._create_widgets()
        self._setup_layout()

    def _create_widgets(self):
        """設定ダイアログのウィジェット作成"""
        # OpenAI API Key設定
        self.api_key_var = tk.StringVar(value=self.openai_api_key)
        self.api_key_frame = ttk.LabelFrame(self, text="OpenAI API Key", padding=5)
        self.api_key_entry = ttk.Entry(self.api_key_frame, textvariable=self.api_key_var, show="*")
        
        # Gemini API Key設定
        self.gemini_api_key_var = tk.StringVar(value=self.gemini_api_key)
        self.gemini_api_key_frame = ttk.LabelFrame(self, text="Gemini API Key", padding=5)
        self.gemini_api_key_entry = ttk.Entry(self.gemini_api_key_frame, textvariable=self.gemini_api_key_var, show="*")
        
        # 書き起こし方式設定
        self.transcription_frame = ttk.LabelFrame(self, text="書き起こし方式", padding=5)
        self.transcription_var = tk.StringVar(value=self.transcription_method)
        self.transcription_whisper = ttk.Radiobutton(
            self.transcription_frame,
            text="Whisper + GPT-4方式（2段階処理）",
            value="whisper_gpt4",
            variable=self.transcription_var
        )
        self.transcription_gpt4audio = ttk.Radiobutton(
            self.transcription_frame,
            text="GPT-4 Audio方式（一括処理）",
            value="gpt4_audio",
            variable=self.transcription_var
        )
        self.transcription_gemini = ttk.Radiobutton(
            self.transcription_frame,
            text="Gemini方式（一括処理）",
            value="gemini",
            variable=self.transcription_var
        )
        
        # 分割時間設定
        self.segment_length_frame = ttk.LabelFrame(self, text="Geminiの場合のみ-分割処理用の秒数", padding=5)
        self.segment_length_var = tk.StringVar(value=str(self.segment_length))
        self.segment_length_entry = ttk.Entry(self.segment_length_frame, textvariable=self.segment_length_var)
        
        # 出力ディレクトリ設定
        self.output_dir_var = tk.StringVar(value=self.output_dir)
        self.output_dir_frame = ttk.LabelFrame(self, text="出力ディレクトリ", padding=5)
        self.output_dir_entry = ttk.Entry(self.output_dir_frame, textvariable=self.output_dir_var)
        self.output_dir_button = ttk.Button(
            self.output_dir_frame,
            text="参照",
            command=self._browse_output_dir
        )
        
        # デバッグモード設定
        self.debug_var = tk.BooleanVar(value=self.debug_mode)
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
        # OpenAI API Key設定
        self.api_key_frame.pack(fill=tk.X, padx=10, pady=5)
        self.api_key_entry.pack(fill=tk.X, padx=5)
        
        # Gemini API Key設定
        self.gemini_api_key_frame.pack(fill=tk.X, padx=10, pady=5)
        self.gemini_api_key_entry.pack(fill=tk.X, padx=5)
        
        # 書き起こし方式設定
        self.transcription_frame.pack(fill=tk.X, padx=10, pady=5)
        self.transcription_whisper.pack(fill=tk.X, padx=5, pady=2)
        self.transcription_gpt4audio.pack(fill=tk.X, padx=5, pady=2)
        self.transcription_gemini.pack(fill=tk.X, padx=5, pady=2)
        
        # 分割時間設定
        self.segment_length_frame.pack(fill=tk.X, padx=10, pady=5)
        self.segment_length_entry.pack(fill=tk.X, padx=5)
        
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
        """出力ディレクトリを選択するダイアログを表示"""
        current_dir = self.output_dir_var.get() or os.path.expanduser("~/Documents/議事録")
        if not os.path.exists(current_dir):
            current_dir = os.path.expanduser("~/Documents")
        
        directory = filedialog.askdirectory(
            initialdir=current_dir,
            title="出力ディレクトリの選択"
        )
        
        if directory:  # ユーザーがディレクトリを選択した場合
            self.output_dir_var.set(directory)

    def _save_settings(self):
        """設定を保存"""
        try:
            # 分割時間の検証
            try:
                segment_length = int(self.segment_length_var.get())
                if segment_length <= 0:
                    raise ValueError("分割時間は正の整数である必要があります")
            except ValueError as e:
                messagebox.showerror("エラー", f"分割時間の設定が不正です: {str(e)}")
                return

            # 設定の更新
            config_manager.update_config({
                "openai_api_key": self.api_key_var.get(),
                "gemini_api_key": self.gemini_api_key_var.get(),
                "debug_mode": self.debug_var.get(),
                "output": {
                    "default_dir": self.output_dir_var.get()
                },
                "transcription": {
                    "method": self.transcription_var.get(),
                    "segment_length_seconds": segment_length
                }
            })
            
            messagebox.showinfo("設定", "設定を保存しました")
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("エラー", f"設定の保存中にエラーが発生しました：{str(e)}") 