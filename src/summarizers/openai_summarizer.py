import logging
from typing import Optional
from ..utils.Common_OpenAIAPI import generate_chat_response, APIError
from ..utils.summarizer import Summarizer

logger = logging.getLogger(__name__)

class OpenAISummarizer(Summarizer):
    """OpenAI APIを使用した議事録生成クラス"""

    def __init__(self):
        """Initialize OpenAI summarizer"""
        super().__init__()
        logger.info("OpenAI Summarizerを初期化しました")

    def summarize(self, text: str, prompt: str) -> str:
        """
        テキストを要約して議事録を生成する

        Args:
            text (str): 要約対象のテキスト
            prompt (str): 要約のためのプロンプト

        Returns:
            str: 生成された議事録

        Raises:
            APIError: API呼び出しに失敗した場合
        """
        try:
            logger.info("OpenAI APIを使用して議事録生成を開始します")
            response = generate_chat_response(
                system_prompt=prompt,
                user_message_content=text
            )
            logger.info(f"議事録生成が完了しました（{len(response)}文字）")
            return response

        except APIError as e:
            error_msg = f"OpenAI APIでの議事録生成に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise 