from .base_title_generator import BaseTitleGenerator, TitleGenerationError
from ...utils.Common_OpenAIAPI import generate_meeting_title, APIError

class GPTTitleGenerator(BaseTitleGenerator):
    """OpenAI GPT-4を使用した会議タイトル生成クラス"""
    
    def generate_title(self, text: str) -> str:
        """
        GPT-4を使用して会議タイトルを生成する

        Args:
            text (str): 会議の書き起こしテキスト

        Returns:
            str: 生成された会議タイトル

        Raises:
            TitleGenerationError: タイトル生成に失敗した場合
        """
        try:
            self.logger.info("GPT-4でタイトル生成を開始")
            title = generate_meeting_title(text)
            
            if not title:
                raise TitleGenerationError("生成されたタイトルが空です")
            
            self.logger.info(f"タイトル生成完了: {title}")
            return title
            
        except APIError as e:
            error_msg = f"OpenAI APIでのタイトル生成に失敗: {str(e)}"
            self.logger.error(error_msg)
            raise TitleGenerationError(error_msg)
        except Exception as e:
            error_msg = f"タイトル生成中に予期せぬエラーが発生: {str(e)}"
            self.logger.error(error_msg)
            raise TitleGenerationError(error_msg) 