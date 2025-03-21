import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from src.utils.config import config_manager

from .summarizer import Summarizer
from ..summarizers.openai_summarizer import OpenAISummarizer
from ..summarizers.gemini_summarizer import GeminiSummarizer

logger = logging.getLogger(__name__)

class SummarizerFactoryError(Exception):
    """Summarizer生成に関連するエラーを扱うカスタム例外クラス"""
    pass

class SummarizerFactory:
    """議事録生成クラスのファクトリ"""

    @staticmethod
    def create_summarizer() -> Summarizer:
        """
        設定に基づいて適切なSummarizerインスタンスを生成する

        Returns:
            Summarizer: 生成されたSummarizerインスタンス

        Raises:
            SummarizerFactoryError: Summarizerの生成に失敗した場合
        """
        try:
            # 設定ファイルの取得（config_managerによるパス解決・PyInstaller対応）
            try:
                config = config_manager.get_config()
                logger.debug(f"読み込まれた設定: {config}")
                logger.debug(f"設定のすべての属性: {dir(config)}")
                
                # summarization属性の有無を確認
                has_summarization = hasattr(config, 'summarization')
                logger.debug(f"summarization属性があるか: {has_summarization}")
                
                # 代替として直接設定ファイルの内容を確認
                config_file = config_manager.config_file
                if config_file.exists():
                    with open(config_file, "r", encoding="utf-8") as f:
                        raw_config = json.load(f)
                        logger.debug(f"設定ファイルの生データ: {raw_config}")
                        logger.debug(f"summarizationセクションの内容: {raw_config.get('summarization', 'なし')}")
            except Exception as e:
                logger.warning(f"設定ファイルの読み込みに失敗しました: {str(e)}")
                logger.info("デフォルトのGeminiSummarizerを使用します")
                return GeminiSummarizer()

            # 議事録生成モデルの取得（デフォルトはGemini）
            model = config.summarization.model
            logger.info(f"議事録生成モデル: {model}")

            # モデルに応じたSummarizerインスタンスを生成
            if model == "openai":
                return OpenAISummarizer()
            elif model == "gemini":
                return GeminiSummarizer()
            else:
                raise SummarizerFactoryError(f"未対応の議事録生成モデル: {model}")

        except Exception as e:
            error_msg = f"Summarizerの生成に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise SummarizerFactoryError(error_msg) 