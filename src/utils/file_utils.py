import os
#import json
import re
from typing import Optional

class FileUtils:
    def get_meeting_title(self, file_path: str) -> str:
        """
        テキストファイルから会議タイトルを抽出
        Args:
            file_path (str): テキストファイルのパス
        Returns:
            str: 会議タイトル
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # 正規表現でタイトルを探す
                title_patterns = [
                    r'"title":\s*"([^"]+)"',         # "title": "XXX" 形式
                    r'"meeting_title":\s*"([^"]+)"',  # "meeting_title": "XXX" 形式
                    r'会議タイトル[:：]\s*(.+)',      # 日本語形式
                    r'タイトル[:：]\s*(.+)',          # 簡略形式
                    r'件名[:：]\s*(.+)',              # 別形式
                ]
                
                for pattern in title_patterns:
                    match = re.search(pattern, content)
                    if match:
                        return match.group(1).strip()
                
                # 最初の行から意味のある文字列を抽出
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith(('#', '//', '{')):
                        return line[:50]  # 最大50文字まで
                
            return '未定義会議'
        except Exception as e:
            print(f"会議タイトルの取得に失敗: {str(e)}")
            return '未定義会議'

    def create_dated_folder(self, base_dir: str, folder_name: str) -> str:
        """
        日付付きフォルダを作成（重複時は連番付与）
        Args:
            base_dir (str): 基準ディレクトリ
            folder_name (str): フォルダ名
        Returns:
            str: 作成されたフォルダのパス
        """
        # 特殊文字の除去
        folder_name = self._sanitize_filename(folder_name)
        folder_path = os.path.join(base_dir, folder_name)

        # 重複チェックと連番付与
        if os.path.exists(folder_path):
            folder_path = self._get_next_available_name(folder_path)

        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    def _sanitize_filename(self, filename: str) -> str:
        """
        ファイル名から使用できない文字を除去
        Args:
            filename (str): 元のファイル名
        Returns:
            str: サニタイズされたファイル名
        """
        return re.sub(r'[\\/:*?"<>|]', '', filename)

    def _get_next_available_name(self, base_path: str) -> str:
        """
        重複しない名前を生成
        Args:
            base_path (str): 基準パス
        Returns:
            str: 重複しないパス
        """
        counter = 1
        while os.path.exists(f"{base_path}_{counter}"):
            counter += 1
        return f"{base_path}_{counter}" 