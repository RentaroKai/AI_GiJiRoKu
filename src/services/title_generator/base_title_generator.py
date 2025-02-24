import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)

class TitleGenerationError(Exception):
    """タイトル生成処理関連のエラーを扱うカスタム例外クラス"""
    pass

class BaseTitleGenerator(ABC):
    """会議タイトル生成の基底クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @abstractmethod
    def generate_title(self, text: str) -> str:
        """
        会議の書き起こしテキストからタイトルを生成する

        Args:
            text (str): 会議の書き起こしテキスト

        Returns:
            str: 生成された会議タイトル

        Raises:
            TitleGenerationError: タイトル生成に失敗した場合
        """
        pass 