import base64
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Iterator
import json
import time

from google import genai
from google.genai import types
from ..utils.config import config_manager

logger = logging.getLogger(__name__)

# デフォルトのモデル設定
DEFAULT_TRANSCRIPTION_MODEL = config_manager.get_model("gemini_transcription")
DEFAULT_MINUTES_MODEL = config_manager.get_model("gemini_minutes")
DEFAULT_TITLE_MODEL = config_manager.get_model("gemini_title")

MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒
MAX_FILE_SIZE_MB = 100  # デフォルトの最大ファイルサイズ（MB）

class MediaType:
    """サポートされるメディアタイプの定数"""
    AUDIO = "audio"
    VIDEO = "video"

class GeminiAPIError(Exception):
    """Gemini API処理中のエラーを表すカスタム例外"""
    pass

class VideoFileTooLargeError(GeminiAPIError):
    """動画ファイルサイズが大きすぎる場合のエラー"""
    pass

class NewGeminiAPI:
    """新しいGemini APIクライアント"""
    
    def __init__(
        self,
        transcription_model: str = None,
        minutes_model: str = None,
        title_model: str = None,
        max_file_size_mb: int = None
    ):
        """Gemini APIクライアントを初期化
        
        Args:
            transcription_model (str, optional): 書き起こし用のモデル名
            minutes_model (str, optional): 議事録まとめ用のモデル名
            title_model (str, optional): タイトル生成用のモデル名
            max_file_size_mb (int, optional): 最大ファイルサイズ（MB）
        """
        # 設定の読み込み
        config = config_manager.get_config()
        
        # 環境変数を優先、なければ設定ファイルからAPIキーを取得
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or config.get("gemini_api_key", "")
        
        if not self.api_key:
            error_msg = "Gemini API keyが設定されていません。環境変数GEMINI_API_KEY、GOOGLE_API_KEY、または設定ファイルのgemini_api_keyを設定してください。"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)
        
        # モデル名の設定（引数 → 設定ファイル → デフォルト値の優先順）
        self.transcription_model = transcription_model or config.get("models", {}).get("gemini_transcription", DEFAULT_TRANSCRIPTION_MODEL)
        self.minutes_model = minutes_model or config.get("models", {}).get("gemini_minutes", DEFAULT_MINUTES_MODEL)
        self.title_model = title_model or config.get("models", {}).get("gemini_title", DEFAULT_TITLE_MODEL)
        
        # 最大ファイルサイズの設定
        self.max_file_size_mb = max_file_size_mb or config.get("max_file_size_mb", MAX_FILE_SIZE_MB)
        
        # クライアントの初期化
        self.client = genai.Client(api_key=self.api_key)
        
        logger.info(f"NewGeminiAPI initialized - Transcription model: {self.transcription_model}")
        logger.info(f"Minutes model: {self.minutes_model}, Title model: {self.title_model}")
        logger.info(f"Max file size: {self.max_file_size_mb} MB")

    def _check_file_size(self, file_path: str) -> None:
        """ファイルサイズをチェックし、大きすぎる場合は例外を発生
        
        Args:
            file_path (str): チェックするファイルのパス
            
        Raises:
            VideoFileTooLargeError: ファイルサイズが制限を超えている場合
            FileNotFoundError: ファイルが存在しない場合
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")
        
        file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            raise VideoFileTooLargeError(
                f"ファイルサイズ({file_size_mb:.1f}MB)が制限({self.max_file_size_mb}MB)を超えています。"
                "ファイルを小さく分割するか、設定の'max_file_size_mb'を増やしてください。"
            )

    def upload_file(self, file_path: str) -> Any:
        """ファイルをGemini APIにアップロード
        
        Args:
            file_path (str): アップロードするファイルのパス
            
        Returns:
            Any: アップロードされたファイルオブジェクト
            
        Raises:
            GeminiAPIError: アップロードに失敗した場合
        """
        try:
            # ファイルサイズのチェック
            self._check_file_size(file_path)
            
            # ファイルをアップロード
            logger.info(f"Uploading file: {file_path}")
            uploaded_file = self.client.files.upload(file=file_path)
            logger.info(f"File uploaded successfully: {uploaded_file.uri}")
            
            return uploaded_file
        except VideoFileTooLargeError:
            raise
        except Exception as e:
            error_msg = f"ファイルのアップロードに失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)

    def transcribe(
        self, 
        file_path: str, 
        media_type: str = MediaType.AUDIO,
        stream: bool = False
    ) -> Union[str, Iterator[str]]:
        """音声または動画ファイルを文字起こし
        
        Args:
            file_path (str): 文字起こしするファイルのパス
            media_type (str): メディアタイプ（'audio' or 'video'）
            stream (bool): ストリーミングレスポンスを返すかどうか
            
        Returns:
            Union[str, Iterator[str]]: 文字起こしテキスト
            
        Raises:
            GeminiAPIError: 文字起こしに失敗した場合
        """
        try:
            uploaded_file = self.upload_file(file_path)
            
            # 文字起こし用のプロンプト
            system_prompt = """議事録を作成して 以下のJSON形式で出力：
{
  "conversations": [
    {
      "speaker": "発言者名",
      "utterance": "発言内容"
    },
    ...
  ]
}
"""
            
            # コンテンツの準備
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_uri(
                            file_uri=uploaded_file.uri,
                            mime_type=uploaded_file.mime_type,
                        ),
                    ],
                ),
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=system_prompt),
                    ],
                ),
            ]
            
            # 応答生成設定
            generate_content_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                response_mime_type="application/json",
            )
            
            logger.info(f"Transcribing {media_type} file using {self.transcription_model}")
            
            # 応答を生成（ストリーミングまたは通常）
            if stream:
                return self._transcribe_stream(contents, generate_content_config)
            else:
                return self._transcribe_normal(contents, generate_content_config)
                
        except Exception as e:
            error_msg = f"{media_type.capitalize()}ファイルの文字起こしに失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)
        finally:
            # アップロードしたファイルの削除を試みる
            try:
                if 'uploaded_file' in locals():
                    # ファイルの削除がサポートされている場合
                    if hasattr(uploaded_file, 'delete'):
                        uploaded_file.delete()
                        logger.info(f"Uploaded file deleted: {uploaded_file.uri}")
            except Exception as e:
                logger.warning(f"アップロードファイルの削除に失敗しました: {str(e)}")

    def _transcribe_stream(self, contents: List[types.Content], config: types.GenerateContentConfig) -> Iterator[str]:
        """文字起こしをストリーミングモードで実行
        
        Args:
            contents (List[types.Content]): コンテンツリスト
            config (types.GenerateContentConfig): 生成設定
            
        Returns:
            Iterator[str]: 文字起こしテキストのストリーム
        """
        try:
            for chunk in self.client.models.generate_content_stream(
                model=self.transcription_model,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            error_msg = f"ストリーミング文字起こしに失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)

    def _transcribe_normal(self, contents: List[types.Content], config: types.GenerateContentConfig) -> str:
        """文字起こしを通常モードで実行
        
        Args:
            contents (List[types.Content]): コンテンツリスト
            config (types.GenerateContentConfig): 生成設定
            
        Returns:
            str: 文字起こしテキスト
        """
        try:
            response = self.client.models.generate_content(
                model=self.transcription_model,
                contents=contents,
                config=config,
            )
            
            if not response.text:
                raise GeminiAPIError("Gemini APIからの応答が空です")
                
            return response.text
        except Exception as e:
            error_msg = f"文字起こしに失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)

    def generate_title(self, transcription_text: str) -> str:
        """会議の書き起こしからタイトルを生成
        
        Args:
            transcription_text (str): 会議の書き起こしテキスト
            
        Returns:
            str: 生成されたタイトル
            
        Raises:
            GeminiAPIError: タイトル生成に失敗した場合
        """
        try:
            # タイトル生成用の設定
            title_config = types.GenerateContentConfig(
                temperature=1.0,
                top_p=0.95,
                top_k=40,
                max_output_tokens=100,
                response_mime_type="application/json",
            )
            
            # タイトル生成用のプロンプト
            system_prompt = "会議の書き起こしからこの会議のメインとなる議題が何だったのかを教えて。JSON形式で {\"title\": \"会議タイトル\"} と出力してください。"
            
            # コンテンツ準備
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=transcription_text),
                        types.Part.from_text(text=system_prompt),
                    ],
                ),
            ]
            
            logger.info(f"Generating title using {self.title_model}")
            
            # タイトル生成
            response = self.client.models.generate_content(
                model=self.title_model,
                contents=contents,
                config=title_config,
            )
            
            if not response.text:
                raise GeminiAPIError("タイトル生成からの応答が空です")
            
            # JSONパースとタイトル抽出
            try:
                response_data = json.loads(response.text)
                title = response_data.get("title", "").strip()
                
                if not title:
                    logger.warning("生成されたタイトルが空です。デフォルトのタイトルを使用します。")
                    title = "会議録"
                
                logger.info(f"Generated title: {title}")
                return title
                
            except json.JSONDecodeError:
                # JSON解析に失敗した場合、テキストをそのまま返す
                cleaned_text = response.text.strip()
                logger.warning(f"JSONパースに失敗しました。テキストをタイトルとして使用: {cleaned_text}")
                return cleaned_text
                
        except Exception as e:
            error_msg = f"タイトル生成に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)

    def generate_minutes(self, transcription_text: str) -> str:
        """会議の書き起こしから議事録を生成
        
        Args:
            transcription_text (str): 会議の書き起こしテキスト
            
        Returns:
            str: 生成された議事録
            
        Raises:
            GeminiAPIError: 議事録生成に失敗した場合
        """
        try:
            # 議事録生成用の設定
            minutes_config = types.GenerateContentConfig(
                temperature=1.0,
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
                response_mime_type="text/plain",
            )
            
            # 議事録生成用のプロンプト
            system_prompt = """以下の会議の書き起こしを要約し、議事録を作成してください。
以下の点に注意して作成してください：
1. 重要な議論のポイントを漏らさない
2. 決定事項を明確にする
3. 次回までのアクションアイテムを箇条書きにする
4. 全体の文脈を保ちながら、簡潔に要約する

Markdownフォーマットで出力してください。"""
            
            # コンテンツ準備
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=transcription_text),
                        types.Part.from_text(text=system_prompt),
                    ],
                ),
            ]
            
            logger.info(f"Generating minutes using {self.minutes_model}")
            
            # 議事録生成
            response = self.client.models.generate_content(
                model=self.minutes_model,
                contents=contents,
                config=minutes_config,
            )
            
            if not response.text:
                raise GeminiAPIError("議事録生成からの応答が空です")
            
            logger.info(f"Generated minutes ({len(response.text)} characters)")
            return response.text
                
        except Exception as e:
            error_msg = f"議事録生成に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg) 