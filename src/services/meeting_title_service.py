import json
import os
import re
from datetime import datetime
from src.utils.file_utils import FileUtils
from src.utils.Common_OpenAIAPI import generate_meeting_title

class MeetingTitleService:
    def __init__(self):
        """
        MeetingTitleServiceの初期化
        FileUtilsのインスタンスを作成
        """
        self.file_utils = FileUtils()

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
            # タイトルをJSON形式で保存
            title_data = {"title": title}
            with open(title_file_path, 'w', encoding='utf-8') as f:
                json.dump(title_data, f, ensure_ascii=False, indent=2)
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
            # 1. ファイル読み込み
            transcript_text = self._read_transcript_file(transcript_file_path)
            
            # 2. タイトル生成
            print("Generating meeting title...")
            title = generate_meeting_title(transcript_text)
            print(f"Generated title: {title}")
            
            # 3. タイトルファイル生成
            timestamp = self._extract_timestamp(transcript_file_path)
            title_file_path = self._generate_title_file_path(timestamp)
            
            # 4. タイトル保存
            self._save_title(title_file_path, title)
            
            return title_file_path
            
        except Exception as e:
            error_msg = f"Error in title generation process: {str(e)}"
            print(error_msg)
            raise 