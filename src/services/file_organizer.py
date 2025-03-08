import os
import shutil
import json
import logging
from datetime import datetime
from typing import List, Dict
from pathlib import Path
from ..utils.file_utils import FileUtils
from ..utils.config import config_manager

class FileOrganizer:
    def __init__(self, debug_mode: bool = False):
        """
        ファイル整理機能の初期化
        Args:
            debug_mode (bool): デバッグモードフラグ
        """
        self.debug_mode = debug_mode
        self.file_utils = FileUtils()
        self.config = config_manager.get_config()
        self.logger = logging.getLogger(__name__)

    def get_output_directory(self) -> str:
        """
        出力ディレクトリを取得する
        設定ファイルから出力ディレクトリを取得し、存在と書き込み権限を確認する
        Returns:
            str: 出力ディレクトリのパス
        """
        try:
            # 設定から出力ディレクトリを取得
            output_dir = self.config.output.default_dir
            if not output_dir or output_dir == "output":
                # デフォルト値の場合はマイドキュメント/議事録を使用
                documents_path = os.path.expanduser("~/Documents")
                output_dir = os.path.join(documents_path, "議事録")

            # ディレクトリの存在確認
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                print(f"出力ディレクトリを作成しました: {output_dir}")
                self.logger.info(f"出力ディレクトリを作成しました: {output_dir}")

            # 書き込み権限の確認
            if not os.access(output_dir, os.W_OK):
                error_msg = f"出力ディレクトリ {output_dir} への書き込み権限がありません"
                print(error_msg)
                self.logger.error(error_msg)
                raise PermissionError(error_msg)

            return output_dir

        except Exception as e:
            error_msg = f"出力ディレクトリの取得中にエラーが発生しました: {e}"
            print(error_msg)
            self.logger.error(error_msg)
            raise

    def organize_meeting_files(self, timestamp: str) -> str:
        """
        会議ファイルを整理する
        Args:
            timestamp (str): 処理対象のタイムスタンプ
        Returns:
            str: 作成されたフォルダのパス
        """
        try:
            # 必要なディレクトリの存在確認と作成
            required_dirs = ['output', 'output/transcriptions', 'output/csv', 'output/minutes', 'output/title']
            for dir_path in required_dirs:
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)
                    if self.debug_mode:
                        print(f"[DEBUG] 一時ディレクトリを作成: {dir_path}")

            # 会議タイトルの取得
            meeting_title_file = f"output/title/meetingtitle_{timestamp}.txt"
            if not os.path.exists(meeting_title_file):
                if self.debug_mode:
                    print(f"[DEBUG] タイトルファイルが見つかりません: {meeting_title_file}")
                meeting_title = "未定義会議"
            else:
                meeting_title = self.file_utils.get_meeting_title(meeting_title_file)

            # 日付の取得（タイムスタンプから）
            try:
                date = datetime.strptime(timestamp, "%Y%m%d%H%M%S").strftime("%Y-%m-%d")
            except ValueError:
                if self.debug_mode:
                    print(f"[DEBUG] 無効なタイムスタンプ形式: {timestamp}")
                date = datetime.now().strftime("%Y-%m-%d")

            # ユーザー指定の出力ディレクトリを取得
            output_dir = self.get_output_directory()
            
            # 新規フォルダの作成
            folder_name = f"{date}_{meeting_title}"
            new_folder = os.path.join(output_dir, folder_name)
            os.makedirs(new_folder, exist_ok=True)
            print(f"会議フォルダを作成しました: {new_folder}")
            self.logger.info(f"会議フォルダを作成しました: {new_folder}")

            # ファイルのコピーとリネーム、その後元ファイルを削除
            self._copy_rename_and_cleanup_files(timestamp, new_folder, date, meeting_title)

            return new_folder

        except Exception as e:
            error_msg = f"ファイルの整理中にエラーが発生しました: {e}"
            print(error_msg)
            self.logger.error(error_msg)
            if self.debug_mode:
                print(f"[DEBUG] 詳細エラー: {str(e)}")
            return "output"  # エラー時はデフォルトの出力ディレクトリを返す

    def _copy_rename_and_cleanup_files(self, timestamp: str, new_folder: str, date: str, meeting_title: str) -> None:
        """
        ファイルのコピー、リネーム、および元ファイルの削除を行う
        Args:
            timestamp (str): タイムスタンプ
            new_folder (str): 新規フォルダパス
            date (str): 日付
            meeting_title (str): 会議タイトル
        """
        # コピー対象ファイルの定義
        files_to_process = {
            # 元のパターン
            f"output/csv/transcription_summary_{timestamp}.csv": f"{date}_{meeting_title}_発言記録.csv",
            f"output/minutes/transcription_summary_{timestamp}_minutes.md": f"{date}_{meeting_title}_議事録まとめ.md",
            f"output/minutes/{timestamp}_reflection.md": f"{date}_{meeting_title}_振り返り.md",
            f"output/transcriptions/transcription_summary_{timestamp}.txt": f"{date}_{meeting_title}_書き起こし.txt",
            f"output/transcriptions/transcription_{timestamp}.txt": f"{date}_{meeting_title}_書き起こし_raw.txt",
            f"output/title/meetingtitle_{timestamp}.txt": f"{date}_{meeting_title}_タイトル.txt",
            
            # リマップ後のファイル用パターン
            f"output/csv/transcription_summary_{timestamp}_remapped.csv": f"{date}_{meeting_title}_発言記録.csv",
            f"output/minutes/transcription_summary_{timestamp}_remapped_minutes.md": f"{date}_{meeting_title}_議事録まとめ.md",
            f"output/transcriptions/transcription_summary_{timestamp}_remapped.txt": f"{date}_{meeting_title}_書き起こし.txt",
        }

        successful_copies = []

        # ファイルごとの処理
        for src, dst in files_to_process.items():
            try:
                if os.path.exists(src):
                    dst_path = os.path.join(new_folder, dst)
                    self.logger.info(f"ファイルをコピーします: {src} -> {dst_path}")
                    
                    # ファイルのコピー
                    shutil.copy2(src, dst_path)
                    successful_copies.append(src)
                    self.logger.info(f"ファイルのコピーが完了しました: {dst_path}")
                else:
                    self.logger.warning(f"元ファイルが存在しません: {src}")

            except Exception as e:
                error_msg = f"ファイル {src} の処理中にエラーが発生しました: {e}"
                self.logger.error(error_msg)
                continue

        # コピーに成功したファイルの削除
        for src in successful_copies:
            try:
                self.logger.info(f"元ファイルを削除します: {src}")
                os.remove(src)
                self.logger.info(f"元ファイルの削除が完了しました: {src}")
            except Exception as e:
                error_msg = f"ファイル {src} の削除中にエラーが発生しました: {e}"
                self.logger.error(error_msg)

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
        
        self.logger.error(error_message) 