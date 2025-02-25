import os
import sys
import pathlib
import logging
from datetime import datetime
from typing import Dict, Any, Union
from pathlib import Path

from ..utils.summarizer_factory import SummarizerFactory, SummarizerFactoryError
from ..utils.Common_OpenAIAPI import generate_chat_response
from ..utils.prompt_manager import prompt_manager

logger = logging.getLogger(__name__)

class MinutesError(Exception):
    """議事録生成関連のエラーを扱うカスタム例外クラス"""
    pass

class MinutesService:
    """議事録生成サービス"""

    def __init__(self, output_dir: str = "output/minutes", config_path: str = "config/settings.json"):
        """Initialize minutes generation service

        Args:
            output_dir (str): 出力ディレクトリ
            config_path (str): 設定ファイルのパス
        """
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = config_path
        logger.info(f"出力ディレクトリを作成/確認: {self.output_dir}")

    def generate_minutes(self, text: Union[str, Path], prompt_path: str = "src/prompts/minutes.txt") -> Dict[str, Any]:
        """議事録を生成する

        Args:
            text (Union[str, Path]): 書き起こしテキストまたはテキストファイルのパス
            prompt_path (str): プロンプトファイルのパス（互換性のために残す）

        Returns:
            Dict[str, Any]: 生成結果（ファイルパスとメタデータを含む）

        Raises:
            MinutesError: 議事録生成に失敗した場合
        """
        try:
            # 入力がPathオブジェクトの場合、ファイルの内容を読み込む
            if isinstance(text, (str, Path)) and os.path.exists(str(text)):
                logger.info(f"テキストファイルを読み込みます: {text}")
                try:
                    with open(text, 'r', encoding='utf-8') as f:
                        input_text = f.read()
                except UnicodeDecodeError:
                    # UTF-8で失敗した場合、CP932で試行
                    with open(text, 'r', encoding='cp932') as f:
                        input_text = f.read()
                logger.info(f"テキストファイルを読み込みました（{len(input_text)}文字）")

                # 入力ファイル名から既存のタイムスタンプを抽出
                input_path = Path(text)
                if "transcription_summary_" in input_path.stem:
                    timestamp = input_path.stem.split("transcription_summary_")[1]
                else:
                    # タイムスタンプが見つからない場合は現在時刻を使用
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            else:
                input_text = str(text)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

            # プロンプトの読み込み - prompt_managerを使用
            logger.info("議事録プロンプトを取得します")
            prompt = prompt_manager.get_prompt("minutes")
            if not prompt:
                logger.error("議事録プロンプトの取得に失敗しました")
                raise MinutesError("議事録プロンプトの取得に失敗しました")
            logger.info(f"議事録プロンプトを取得しました（{len(prompt)}文字）")

            # Summarizerの生成
            summarizer = SummarizerFactory.create_summarizer(self.config_path)
            logger.info("議事録生成を開始します")

            # 議事録の生成
            minutes = summarizer.summarize(input_text, prompt)

            # 出力ファイルパスの生成（既存の命名規則に合わせる）
            output_path = self.output_dir / f"transcription_summary_{timestamp}_minutes.md"

            # 議事録の保存
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(minutes)

            logger.info(f"議事録を保存しました: {output_path}")

            return {
                "text": minutes,
                "file_path": output_path,
                "timestamp": timestamp
            }

        except Exception as e:
            error_msg = f"議事録の生成に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise MinutesError(error_msg)

    def get_output_path(self, transcription_file: pathlib.Path) -> pathlib.Path:
        """出力ファイルパスの生成"""
        return self.output_dir / f"{transcription_file.stem}_minutes.md"

    def generate_reflection(self, text: str) -> str:
        """
        会議の反省点と改善点を生成する
        
        Args:
            text (str): 議事録のテキスト
        
        Returns:
            str: 反省点と改善点を含む分析結果
        """
        try:
            logging.info("会議の反省点分析を開始します")
            
            if not text:
                logger.error("議事録データが空です")
                raise MinutesError("議事録データが空です")
            
            # プロンプトの読み込み - prompt_managerを使用
            logger.info("反省点プロンプトを取得します")
            prompt_template = prompt_manager.get_prompt("reflection")
            if not prompt_template:
                logger.error("反省点プロンプトの取得に失敗しました")
                raise MinutesError("反省点プロンプトの取得に失敗しました")
            logger.info(f"反省点プロンプトを取得しました（{len(prompt_template)}文字）")
            
            # GPT-4による分析
            reflection_result = generate_chat_response(
                prompt_template,
                text
            )
            
            if not reflection_result:
                error_msg = "反省点の生成結果が空です"
                logging.error(error_msg)
                raise MinutesError(error_msg)
            
            logging.info("反省点分析が完了しました")
            return reflection_result
            
        except Exception as e:
            error_msg = f"反省点分析中にエラーが発生しました: {str(e)}"
            logging.error(error_msg)
            raise MinutesError(error_msg) 