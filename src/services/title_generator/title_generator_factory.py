import logging
from typing import Optional
from .base_title_generator import BaseTitleGenerator
from .gpt_title_generator import GPTTitleGenerator
from .gemini_title_generator import GeminiTitleGenerator

logger = logging.getLogger(__name__)

class TitleGeneratorFactoryError(Exception):
    """タイトルジェネレーターファクトリーのエラーを扱うカスタム例外クラス"""
    pass

class TitleGeneratorFactory:
    """タイトルジェネレーターのファクトリークラス"""
    
    @staticmethod
    def create_generator(transcription_method: str) -> BaseTitleGenerator:
        """
        書き起こし方式に応じたタイトルジェネレーターを生成する

        Args:
            transcription_method (str): 書き起こし方式
                - "whisper_gpt4": Whisper + GPT-4方式
                - "gpt4_audio": GPT-4 Audio方式
                - "gemini": Gemini方式

        Returns:
            BaseTitleGenerator: タイトルジェネレーターのインスタンス

        Raises:
            TitleGeneratorFactoryError: サポートされていない書き起こし方式が指定された場合
        """
        try:
            logger.info(f"タイトルジェネレーターを作成: 書き起こし方式 = {transcription_method}")
            
            if transcription_method in ["whisper_gpt4", "gpt4_audio"]:
                return GPTTitleGenerator()
            elif transcription_method == "gemini":
                return GeminiTitleGenerator()
            else:
                raise TitleGeneratorFactoryError(f"サポートされていない書き起こし方式です: {transcription_method}")
                
        except Exception as e:
            error_msg = f"タイトルジェネレーターの作成に失敗: {str(e)}"
            logger.error(error_msg)
            raise TitleGeneratorFactoryError(error_msg) 