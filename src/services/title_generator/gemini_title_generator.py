from .base_title_generator import BaseTitleGenerator, TitleGenerationError
from ...utils.new_gemini_api import GeminiAPI, GeminiAPIError as TranscriptionError

class GeminiTitleGenerator(BaseTitleGenerator):
    """Google Geminiを使用した会議タイトル生成クラス"""
    
    def __init__(self):
        """Initialize Gemini title generator"""
        super().__init__()
        self.gemini_api = GeminiAPI()
        
        # タイトル生成用のシステムプロンプト
        self.system_prompt = """会議の書き起こしからこの会議のメインとなる議題が何だったのかを教えて。
出力は以下のJSON形式で返してください：
{
    "title": "会議のタイトル"
}

例：
{
    "title": "取引先とカフェの方向性に関する会議"
}
"""
    
    def generate_title(self, text: str) -> str:
        """
        Geminiを使用して会議タイトルを生成する

        Args:
            text (str): 会議の書き起こしテキスト

        Returns:
            str: 生成された会議タイトル

        Raises:
            TitleGenerationError: タイトル生成に失敗した場合
        """
        try:
            self.logger.info("Geminiでタイトル生成を開始")
            
            # Gemini APIを使用してタイトルを生成
            title = self.gemini_api.generate_meeting_title(text)
            
            self.logger.info(f"タイトル生成完了: {title}")
            return title
            
        except TranscriptionError as e:
            error_msg = f"Gemini APIでのタイトル生成に失敗: {str(e)}"
            self.logger.error(error_msg)
            raise TitleGenerationError(error_msg)
        except Exception as e:
            error_msg = f"タイトル生成中にエラーが発生: {str(e)}"
            self.logger.error(error_msg)
            raise TitleGenerationError(error_msg) 