import os
import shutil
import json
from datetime import datetime
from typing import List, Dict
from ..utils.file_utils import FileUtils

class FileOrganizer:
    def __init__(self, debug_mode: bool = False):
        """
        ファイル整理機能の初期化
        Args:
            debug_mode (bool): デバッグモードフラグ
        """
        self.debug_mode = debug_mode
        self.file_utils = FileUtils()

    def organize_meeting_files(self, timestamp: str) -> str:
        """
        会議ファイルを整理する
        Args:
            timestamp (str): 処理対象のタイムスタンプ
        Returns:
            str: 作成されたフォルダのパス
        """
        try:
            # 会議タイトルの取得
            summary_file = f"output/transcriptions/transcription_summary_{timestamp}.txt"
            meeting_title = self.file_utils.get_meeting_title(summary_file)

            # 日付の取得（タイムスタンプから）
            date = datetime.strptime(timestamp, "%Y%m%d%H%M%S").strftime("%Y-%m-%d")

            # 新規フォルダの作成
            folder_name = f"{date}_{meeting_title}"
            new_folder = self.file_utils.create_dated_folder("output", folder_name)

            # ファイルのコピーとリネーム
            self._copy_and_rename_files(timestamp, new_folder, date, meeting_title)

            return new_folder

        except Exception as e:
            self._handle_error(e)
            raise

    def _copy_and_rename_files(self, timestamp: str, new_folder: str, date: str, meeting_title: str) -> None:
        """
        ファイルのコピーとリネーム処理
        Args:
            timestamp (str): タイムスタンプ
            new_folder (str): 新規フォルダパス
            date (str): 日付
            meeting_title (str): 会議タイトル
        """
        # デバッグ用プリント
        print(f"[DEBUG] ファイルリネーム - タイムスタンプ: {timestamp}")
        print(f"[DEBUG] ファイルリネーム - 新規フォルダ: {new_folder}")
        print(f"[DEBUG] ファイルリネーム - 日付: {date}")
        print(f"[DEBUG] ファイルリネーム - 会議タイトル: {meeting_title}")

        # コピー対象ファイルの定義
        files_to_copy = {
            f"output/csv/transcription_summary_{timestamp}.csv": f"{date}_{meeting_title}_発言記録.csv",
            f"output/minutes/transcription_summary_{timestamp}_minutes.md": f"{date}_{meeting_title}_議事録まとめ.md",
            f"output/minutes/{timestamp}_reflection.md": f"{date}_{meeting_title}_振り返り.md"
        }

        # デバッグ用プリント
        print("[DEBUG] コピー対象ファイル:")
        for src, dst in files_to_copy.items():
            print(f"[DEBUG] 元ファイル: {src}")
            print(f"[DEBUG] 新ファイル名: {dst}")
            if os.path.exists(src):
                dst_path = os.path.join(new_folder, dst)
                print(f"[DEBUG] コピー実行: {src} -> {dst_path}")
                shutil.copy2(src, dst_path)
            else:
                print(f"[DEBUG] ファイルが存在しません: {src}")

    def _handle_error(self, error: Exception) -> None:
        """
        エラー処理
        Args:
            error (Exception): 発生したエラー
        """
        if self.debug_mode:
            error_message = f"詳細エラー情報:\n{str(error)}\n{error.__traceback__}"
        else:
            error_message = "ファイルの処理中にエラーが発生しました。"
        
        # TODO: エラーメッセージの表示方法は要検討
        print(error_message)  # 仮の実装 