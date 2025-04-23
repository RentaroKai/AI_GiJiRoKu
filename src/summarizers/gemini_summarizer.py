import logging
from typing import Optional
from ..utils.new_gemini_api import GeminiAPI, GeminiAPIError as TranscriptionError
from ..utils.summarizer import Summarizer
#from ..utils.config import config_manager

logger = logging.getLogger(__name__)

class GeminiSummarizer(Summarizer):
    """Gemini APIを使用した議事録生成クラス"""

    def __init__(self):
        """Initialize Gemini summarizer"""
        super().__init__()
        self.api = GeminiAPI()
        logger.info("Gemini Summarizerを初期化しました")

    def summarize(self, text: str, prompt: str) -> str:
        """
        テキストを要約して議事録を生成する

        Args:
            text (str): 要約対象のテキスト
            prompt (str): 要約のためのプロンプト

        Returns:
            str: 生成された議事録

        Raises:
            TranscriptionError: API呼び出しに失敗した場合
        """
        try:
            logger.info("Gemini APIを使用して議事録生成を開始します")
            response = self.api.summarize_minutes(text, prompt)
            logger.info(f"議事録生成が完了しました（{len(response)}文字）")
            return response

        except TranscriptionError as e:
            error_msg = f"Gemini APIでの議事録生成に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise 