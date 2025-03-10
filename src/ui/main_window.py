import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import pathlib
import threading
#import subprocess
import os
from typing import Optional
from ..services.audio import AudioProcessor, AudioProcessingError
from ..services.transcription import TranscriptionService, TranscriptionError
from ..services.csv_converter import CSVConverterService, CSVConversionError
from ..services.file_organizer import FileOrganizer
from ..utils.config import config_manager, ConfigError
from ..utils.prompt_manager import prompt_manager
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
        self.reflection_var = tk.BooleanVar(value=False)  # Hidden but kept for compatibility
        
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
                "reflection": False  # Always set to False to disable the reflection feature
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
                f"議事録: {results.get('minutes', '未実行')}"
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
        self.resizable(True, True)  # リサイズ可能に変更
        self.geometry("600x700")    # 高さを700pxに増やす
        
        # ウィンドウを親の上に表示
        self.transient(parent)
        self.lift()
        self.grab_set()  # モーダルダイアログとして設定

        # 設定の読み込み
        self.config = self._load_config()
        self.openai_api_key = self.config.get("openai_api_key", "")
        self.gemini_api_key = self.config.get("gemini_api_key", "")
        self.transcription_method = self.config.get("transcription", {}).get("method", "gemini")
        self.summarization_model = self.config.get("summarization", {}).get("model", "gemini")
        self.segment_length = self.config.get("transcription", {}).get("segment_length_seconds", 300)
        self.enable_speaker_remapping = self.config.get("transcription", {}).get("enable_speaker_remapping", True)
        self.output_dir = self.config.get("output", {}).get("default_dir", os.path.expanduser("~/Documents/議事録"))

        # プロンプトの読み込み
        self.minutes_prompt = prompt_manager.get_prompt("minutes")
        self.default_minutes_prompt = prompt_manager.get_default_prompt("minutes")

        self._create_widgets()
        self._layout_widgets()

    def _create_widgets(self):
        """設定ダイアログのウィジェット作成"""
        # タブコントロールの作成
        self.tab_control = ttk.Notebook(self)
        
        # タブのスタイル設定
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[20, 5])  # 左右に20px、上下に5pxのパディングを設定
        
        # 基本設定タブ
        self.basic_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.basic_tab, text="基本設定")
        
        # プロンプト設定タブ
        self.prompt_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.prompt_tab, text="議事録の内容を指定")
        
        # === 基本設定タブのウィジェット ===
        # OpenAI API Key設定
        self.api_key_var = tk.StringVar(value=self.openai_api_key)
        self.api_key_frame = ttk.LabelFrame(self.basic_tab, text="OpenAI API Key", padding=5)
        self.api_key_entry = ttk.Entry(self.api_key_frame, textvariable=self.api_key_var, show="*")
        
        # Gemini API Key設定
        self.gemini_api_key_var = tk.StringVar(value=self.gemini_api_key)
        self.gemini_api_key_frame = ttk.LabelFrame(self.basic_tab, text="Gemini API Key", padding=5)
        self.gemini_api_key_entry = ttk.Entry(self.gemini_api_key_frame, textvariable=self.gemini_api_key_var, show="*")
        
        # 書き起こし方式設定
        self.transcription_frame = ttk.LabelFrame(self.basic_tab, text="書き起こし方式", padding=5)
        self.transcription_var = tk.StringVar(value=self.transcription_method)
        self.transcription_whisper = ttk.Radiobutton(
            self.transcription_frame,
            text="Whisper方式",
            value="whisper_gpt4",
            variable=self.transcription_var
        )
        self.transcription_gpt4audio = ttk.Radiobutton(
            self.transcription_frame,
            text="GPT-4 Audio方式",
            value="gpt4_audio",
            variable=self.transcription_var
        )
        self.transcription_gemini = ttk.Radiobutton(
            self.transcription_frame,
            text="Gemini方式",
            value="gemini",
            variable=self.transcription_var
        )
        
        # 話者置換処理オプション
        self.enable_speaker_remapping_var = tk.BooleanVar(value=self.enable_speaker_remapping)
        self.enable_speaker_remapping_check = ttk.Checkbutton(
            self.transcription_frame,
            text="話者置換処理を有効にする",
            variable=self.enable_speaker_remapping_var
        )
        self.speaker_remapping_label = ttk.Label(
            self.transcription_frame,
            text="バラバラの話者名が（部分的に）統一されます",
            wraplength=350
        )
        
        # 分割時間設定
        self.segment_length_frame = ttk.LabelFrame(self.basic_tab, text="ファイルを何秒ごとに分割処理するか(推奨:300秒)", padding=5)
        self.segment_length_var = tk.StringVar(value=str(self.segment_length))
        self.segment_length_entry = ttk.Entry(self.segment_length_frame, textvariable=self.segment_length_var)

        # 議事録生成モデル設定
        self.summarization_frame = ttk.LabelFrame(self.basic_tab, text="議事録生成モデル", padding=5)
        self.summarization_var = tk.StringVar(value=self.summarization_model)
        self.summarization_openai = ttk.Radiobutton(
            self.summarization_frame,
            text="OpenAI方式",
            value="openai",
            variable=self.summarization_var
        )
        self.summarization_gemini = ttk.Radiobutton(
            self.summarization_frame,
            text="Gemini方式",
            value="gemini",
            variable=self.summarization_var
        )

        # 出力ディレクトリ設定
        self.output_dir_var = tk.StringVar(value=self.output_dir)
        self.output_dir_frame = ttk.LabelFrame(self.basic_tab, text="出力ディレクトリ", padding=5)
        self.output_dir_entry = ttk.Entry(self.output_dir_frame, textvariable=self.output_dir_var)
        self.output_dir_button = ttk.Button(
            self.output_dir_frame,
            text="参照",
            command=self._browse_output_dir
        )

        # === プロンプト設定タブのウィジェット ===
        # 議事録プロンプト設定
        self.minutes_prompt_frame = ttk.LabelFrame(self.prompt_tab, text="議事録生成プロンプト", padding=5)
        self.minutes_prompt_text = scrolledtext.ScrolledText(
            self.minutes_prompt_frame, 
            wrap=tk.WORD,
            width=60,
            height=20
        )
        self.minutes_prompt_text.insert(tk.END, self.minutes_prompt)
        
        # プロンプトリセットボタン
        self.reset_prompt_button = ttk.Button(
            self.minutes_prompt_frame,
            text="デフォルトに戻す",
            command=self._reset_minutes_prompt
        )

        # 保存ボタン
        self.save_button = ttk.Button(self, text="保存", command=self._save_settings)

    def _layout_widgets(self):
        """ウィジェットのレイアウト"""
        # タブコントロールの配置
        self.tab_control.pack(expand=1, fill="both", padx=5, pady=5)
        
        # === 基本設定タブのレイアウト ===
        # OpenAI API Key
        self.api_key_frame.pack(fill="x", padx=5, pady=5)
        self.api_key_entry.pack(fill="x", padx=5, pady=5)
        
        # Gemini API Key
        self.gemini_api_key_frame.pack(fill="x", padx=5, pady=5)
        self.gemini_api_key_entry.pack(fill="x", padx=5, pady=5)
        
        # 書き起こし方式
        self.transcription_frame.pack(fill="x", padx=5, pady=5)
        self.transcription_whisper.pack(anchor="w", padx=5, pady=2)
        self.transcription_gpt4audio.pack(anchor="w", padx=5, pady=2)
        self.transcription_gemini.pack(anchor="w", padx=5, pady=2)
        ttk.Separator(self.transcription_frame, orient="horizontal").pack(fill="x", padx=5, pady=5)
        self.enable_speaker_remapping_check.pack(anchor="w", padx=5, pady=2)
        self.speaker_remapping_label.pack(fill="x", padx=5, pady=2)
        
        # 分割時間
        self.segment_length_frame.pack(fill="x", padx=5, pady=5)
        self.segment_length_entry.pack(fill="x", padx=5, pady=5)

        # 議事録生成モデル
        self.summarization_frame.pack(fill="x", padx=5, pady=5)
        self.summarization_openai.pack(anchor="w", padx=5, pady=2)
        self.summarization_gemini.pack(anchor="w", padx=5, pady=2)

        # 出力ディレクトリ
        self.output_dir_frame.pack(fill="x", padx=5, pady=5)
        self.output_dir_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.output_dir_button.pack(side="left", padx=5)
        
        # === プロンプト設定タブのレイアウト ===
        # 議事録プロンプト
        self.minutes_prompt_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.minutes_prompt_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.reset_prompt_button.pack(anchor="e", padx=5, pady=5)
        
        # 保存ボタン
        self.save_button.pack(pady=10)

    def _reset_minutes_prompt(self):
        """議事録プロンプトをデフォルトに戻す"""
        if messagebox.askyesno("確認", "議事録プロンプトをデフォルトに戻しますか？"):
            self.minutes_prompt_text.delete(1.0, tk.END)
            self.minutes_prompt_text.insert(tk.END, self.default_minutes_prompt)

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
        """設定の保存"""
        try:
            # 設定ファイルの読み込み
            try:
                # prompt_managerが使用するパスと同じパスを使用
                config_file = prompt_manager.config_file
                if config_file.exists():
                    with open(config_file, "r", encoding="utf-8") as f:
                        config = json.load(f)
                else:
                    config = {}
            except (FileNotFoundError, json.JSONDecodeError):
                config = {}

            # 既存の設定を保持しながら新しい設定を更新
            config.update({
                "openai_api_key": self.api_key_var.get(),
                "gemini_api_key": self.gemini_api_key_var.get(),
                "output": {
                    "default_dir": self.output_dir_var.get()
                },                
                "transcription": {
                    "method": self.transcription_var.get(),
                    "segment_length_seconds": int(self.segment_length_var.get()),
                    "enable_speaker_remapping": self.enable_speaker_remapping_var.get()
                },
                "summarization": {
                    "model": self.summarization_var.get()
                },
            })
            
            # 設定ディレクトリが存在しない場合は作成
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 設定を保存
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            # プロンプトの保存
            minutes_prompt_text = self.minutes_prompt_text.get(1.0, tk.END).strip()
            prompt_manager.save_custom_prompt("minutes", minutes_prompt_text)
            
            self.destroy()
            messagebox.showinfo("成功", "設定を保存しました")
            
        except Exception as e:
            messagebox.showerror("エラー", f"設定の保存に失敗しました: {str(e)}")

    def _load_config(self):
        """設定の読み込み"""
        try:
            # prompt_managerが使用するパスと同じパスを使用
            config_file = prompt_manager.config_file
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {} 