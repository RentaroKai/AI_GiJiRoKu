from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class Summarizer(ABC):
    """議事録生成の抽象基底クラス"""
    
    @abstractmethod
    def summarize(self, text: str, prompt: str) -> str:
        """
        テキストを要約して議事録を生成する

        Args:
            text (str): 要約対象のテキスト
            prompt (str): 要約のためのプロンプト

        Returns:
            str: 生成された議事録
        """
        pass 