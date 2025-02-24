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
            
            # 4. タイトル生成
            print("Generating meeting title...")
            title = title_generator.generate_title(transcript_text)
            
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