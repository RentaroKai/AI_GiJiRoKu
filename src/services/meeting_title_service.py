import json
import os
import re
from datetime import datetime
from src.utils.file_utils import FileUtils
from src.utils.config import ConfigManager, config_manager
from .title_generator import TitleGeneratorFactory, TitleGeneratorFactoryError, TitleGenerationError

class MeetingTitleService:
    def __init__(self):
        """
        MeetingTitleServiceの初期化
        FileUtilsのインスタンスを作成
        """
        self.file_utils = FileUtils()
        self.config_manager = config_manager

    def _read_transcript_file(self, transcript_file_path: str) -> str:
        """
        書き起こしファイルを読み込む
        Args:
            transcript_file_path: 書き起こしファイルのパス
        Returns:
            str: 書き起こしテキスト
        """
        print(f"Reading transcript file: {transcript_file_path}")
        try:
            with open(transcript_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            error_msg = f"Transcript file not found: {transcript_file_path}"
            print(error_msg)
            raise FileNotFoundError(error_msg)
        except Exception as e:
            error_msg = f"Error reading transcript file: {str(e)}"
            print(error_msg)
            raise

    def _extract_timestamp(self, transcript_file_path: str) -> str:
        """
        ファイル名からタイムスタンプを抽出
        Args:
            transcript_file_path: 書き起こしファイルのパス
        Returns:
            str: タイムスタンプ（YYYYMMDDhhmmss形式）
        """
        print(f"Extracting timestamp from file: {transcript_file_path}")
        try:
            # transcription_summary_YYYYMMDDhhmmss.txt からタイムスタンプを抽出
            match = re.search(r'_(\d{14})', os.path.basename(transcript_file_path))
            if match:
                return match.group(1)
            raise ValueError(f"Could not extract timestamp from filename: {transcript_file_path}")
        except Exception as e:
            error_msg = f"Error extracting timestamp: {str(e)}"
            print(error_msg)
            raise

    def _generate_title_file_path(self, timestamp: str) -> str:
        """
        タイトルファイルのパスを生成
        Args:
            timestamp: タイムスタンプ
        Returns:
            str: タイトルファイルのパス
        """
        # output/title ディレクトリにタイトルファイルを作成
        return os.path.join("output", "title", f"meetingtitle_{timestamp}.txt")

    def _save_title(self, title_file_path: str, title: str) -> None:
        """
        生成されたタイトルをファイルに保存
        Args:
            title_file_path: 保存先ファイルパス
            title: 生成されたタイトル
        """
        print(f"Saving title to: {title_file_path}")
        try:
            # タイトルをプレーンテキストで保存
            with open(title_file_path, 'w', encoding='utf-8') as f:
                f.write(title)
            print(f"Title saved successfully to: {title_file_path}")
        except Exception as e:
            error_msg = f"Error saving title file: {str(e)}"
            print(error_msg)
            raise

    def process_transcript_and_generate_title(self, transcript_file_path: str) -> str:
        """
        書き起こしファイルからタイトルを生成して保存する統合処理
        Args:
            transcript_file_path: 書き起こしファイルのパス
        Returns:
            str: 生成されたタイトルファイルのパス
        """
        try:
            # 1. 設定から書き起こし方式を取得
            config = self.config_manager.get_config()
            print(f"[DEBUG] process_transcript_and_generate_title - config id: {id(config)}")
            print(f"[DEBUG] process_transcript_and_generate_title - transcription.method: {config.transcription.method}")
            transcription_method = config.transcription.method
            print(f"Using transcription method: {transcription_method}")
            
            # 2. タイトルジェネレーターを作成
            title_generator = TitleGeneratorFactory.create_generator(transcription_method)
            
            # 3. ファイル読み込み
            transcript_text = self._read_transcript_file(transcript_file_path)
            
            # --- 追加: 送信テキスト量の判定と準備 ---
            marker = '"speaker":'
            marker_count = transcript_text.count(marker)
            text_for_title = transcript_text  # デフォルトは全文

            if marker_count == 0:
                print(f"[WARN] 発話者マーカー '{marker}' が見つかりませんでした。全文を送信します。")
            elif marker_count > 60:  # 30から60に変更
                print(f"[INFO] 発話者マーカーの出現回数が {marker_count} 回 (>60) です。")
                # 61回目のマーカーの位置を見つける
                current_index = -1
                found_count = 0
                for i in range(60):  # 30から60に変更
                    current_index = transcript_text.find(marker, current_index + 1)
                    if current_index == -1:
                        # 60回見つかる前に終端に達した場合 (予期せぬケース)
                        print(f"[WARN] 60回目の発話者マーカーが見つかりませんでした（{i+1}回目まで検出）。全文を使用します。")
                        text_for_title = transcript_text # 念のため全文に戻す
                        found_count = -1 # ループ脱出と後続処理のスキップフラグ
                        break
                    found_count = i + 1
                
                if found_count == 60: # 60回目が見つかった場合のみカット
                    cutoff_index = current_index
                    text_for_title = transcript_text[:cutoff_index]
                    print(f"[INFO] 60回目の '{marker}' 以降を削除して送信します (切り詰め後 {len(text_for_title)} 文字)。")
            
            else: # 1 <= marker_count <= 60 の場合
                print(f"[INFO] 発話者マーカーの出現回数が {marker_count} 回 (<=60) のため、全文を使用します。")
            # --- 追加ここまで ---
            
            # 4. タイトル生成
            print("Generating meeting title...")
            # 修正: title_generator に渡すテキストを変更
            title = title_generator.generate_title(text_for_title)
            
            # JSONとして解析できない場合は、テキストとして扱う
            try:
                title_json = json.loads(title)
                title = title_json.get("title", title)
            except json.JSONDecodeError:
                print("JSONパースに失敗。テキストベースの抽出を試みます")
            
            print(f"Generated title: {title}")
            
            # 5. タイトルファイル生成
            timestamp = self._extract_timestamp(transcript_file_path)
            title_file_path = self._generate_title_file_path(timestamp)
            
            # タイトル保存前にディレクトリを作成
            os.makedirs(os.path.dirname(title_file_path), exist_ok=True)
            
            # 6. タイトル保存
            self._save_title(title_file_path, title)
            
            return title_file_path
            
        except (TitleGeneratorFactoryError, TitleGenerationError) as e:
            error_msg = f"Error in title generation process: {str(e)}"
            print(error_msg)
            raise
        except Exception as e:
            error_msg = f"Unexpected error in title generation process: {str(e)}"
            print(error_msg)
            raise 