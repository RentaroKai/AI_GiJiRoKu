import base64
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Iterator
import json
import time
import httplib2

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

# 互換性のために既存の例外クラス名も保持
TranscriptionError = GeminiAPIError

class VideoFileTooLargeError(GeminiAPIError):
    """動画ファイルサイズが大きすぎる場合のエラー"""
    pass

class GeminiAPI:
    """Gemini APIクライアント"""
    
    def __init__(
        self,
        transcription_model: str = None,
        minutes_model: str = None,
        title_model: str = None,
        max_file_size_mb: int = None,
        api_key: str = None
    ):
        """Gemini APIクライアントを初期化
        
        Args:
            transcription_model (str, optional): 書き起こし用のモデル名
            minutes_model (str, optional): 議事録まとめ用のモデル名
            title_model (str, optional): タイトル生成用のモデル名
            max_file_size_mb (int, optional): 最大ファイルサイズ（MB）
            api_key (str, optional): 直接指定するAPIキー
        """
        # SSL証明書の設定（互換性のため）
        cert_path = os.environ.get('SSL_CERT_FILE')
        if cert_path:
            httplib2.CA_CERTS = cert_path
            logger.info(f"SSL証明書が設定されました: {cert_path}")
            
        # 設定の読み込み
        config = config_manager.get_config()
        
        # APIキーを取得（優先順位: 引数 > 環境変数 > 設定ファイル）
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or config.gemini_api_key
        
        if not self.api_key:
            error_msg = "Gemini API keyが設定されていません。環境変数GEMINI_API_KEY、GOOGLE_API_KEY、または設定ファイルのgemini_api_keyを設定してください。"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)
        
        # モデル名の設定（引数 → 設定ファイル → デフォルト値の優先順）
        self.transcription_model = transcription_model or getattr(config.models, "gemini_transcription", DEFAULT_TRANSCRIPTION_MODEL)
        self.minutes_model = minutes_model or getattr(config.models, "gemini_minutes", DEFAULT_MINUTES_MODEL)
        self.title_model = title_model or getattr(config.models, "gemini_title", DEFAULT_TITLE_MODEL)
        
        # 最大ファイルサイズの設定
        self.max_file_size_mb = max_file_size_mb or getattr(config, "max_file_size_mb", MAX_FILE_SIZE_MB)
        
        # クライアントの初期化 - 新しいGemini APIスタイル
        self.client = genai.Client(api_key=self.api_key)
        
        # 互換性のための設定
        self.generation_config = {
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }
        
        # タイトル生成用の設定
        self.title_generation_config = {
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 100,
            "response_mime_type": "application/json",
        }
        
        # 議事録生成用の設定
        self.minutes_generation_config = {
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
        }
        
        # システムプロンプト（互換性のため）
        self.system_prompt = """あなたは会議の書き起こしを行う専門家です。
以下の点に注意して、音声ファイルに忠実な書き起こしテキストを作成してください：
1. 声色と発言内容から発言者を判定する
2. 発言者と発言内容を分けて表示
3. 発言の整形は最小限にとどめ、発言をそのまま書き起こす
4. 以下のJSON形式で出力：
{
  "conversations": [
    {
      "speaker": "発言者名",
      "utterance": "発言内容"
    },
    ...
  ]
}

入力された音声の書き起こしテキストを上記の形式に変換してください。 。"""
        
        # タイトル生成用のシステムプロンプト
        self.title_system_prompt = """会議の書き起こしからこの会議のメインとなる議題が何だったのかを教えて。例：取引先とカフェの方向性に関する会議"""
        
        logger.info(f"GeminiAPI initialized - Transcription model: {self.transcription_model}")
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

    def upload_file(self, file_path: str, mime_type: Optional[str] = None) -> Any:
        """ファイルをGemini APIにアップロード
        
        Args:
            file_path (str): アップロードするファイルのパス
            mime_type (str, optional): ファイルのMIMEタイプ (非推奨、新APIでは自動検出)
            
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
            
            # コンテンツとして、アップロードしたファイルとプロンプトを渡す
            contents = [
                uploaded_file,
                system_prompt
            ]
            
            # 温度や最大トークン数などのパラメータ設定
            generation_config = {
                "temperature": 0.1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "application/json",
            }
            
            logger.info(f"Transcribing {media_type} file using {self.transcription_model}")
            
            # 応答を生成（ストリーミングまたは通常）
            if stream:
                return self._transcribe_stream(contents, config=generation_config)
            else:
                return self._transcribe_normal(contents, config=generation_config)
                
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

    def transcribe_audio(self, audio_file_path: str, system_prompt: str = None) -> str:
        """音声ファイルを文字起こしする（既存APIとの互換性のためのメソッド）
        
        Args:
            audio_file_path (str): 音声ファイルのパス
            system_prompt (str, optional): 文字起こし用のシステムプロンプト
            
        Returns:
            str: 文字起こしテキスト
            
        Raises:
            GeminiAPIError: 文字起こしに失敗した場合
        """
        try:
            # 新しいAPIを使用して文字起こし
            result = self.transcribe(audio_file_path, media_type=MediaType.AUDIO)
            return result
        except Exception as e:
            error_msg = f"音声ファイルの文字起こしに失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)

    def _transcribe_stream(self, contents: List, config: Dict) -> Iterator[str]:
        """文字起こしをストリーミングモードで実行
        
        Args:
            contents (List): コンテンツリスト
            config (Dict): 生成設定
            
        Returns:
            Iterator[str]: 文字起こしテキストのストリーム
        """
        try:
            # 新しいストリーミングAPI呼び出し方式
            for chunk in self.client.models.generate_content_stream(
                model=self.transcription_model,
                contents=contents,
                config=config,
            ):
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text
        except Exception as e:
            error_msg = f"ストリーミング文字起こしに失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)

    def _transcribe_normal(self, contents: List, config: Dict) -> str:
        """文字起こしを通常モードで実行
        
        Args:
            contents (List): コンテンツリスト
            config (Dict): 生成設定
            
        Returns:
            str: 文字起こしテキスト
        """
        try:
            # 新しいAPI呼び出し方式
            response = self.client.models.generate_content(
                model=self.transcription_model,
                contents=contents,
                config=config,
            )
            
            if hasattr(response, 'text') and response.text:
                return response.text
            else:
                raise GeminiAPIError("Gemini APIからの応答が空です")
                
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
            title_config = {
                "temperature": 0.1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 200,
                "response_mime_type": "application/json",
            }
            
            # タイトル生成用のプロンプト
            system_prompt =  """
会議の書き起こしからこの会議のメインとなる議題が何だったのかを短くまとめて下記のフォーマットで出力せよ。
JSON形式で。
{
    "title": "会議タイトル"
}

"""
            
            # コンテンツ準備
            contents = [
                transcription_text,
                system_prompt
            ]
            
            logger.info(f"Generating title using {self.title_model}")
            
            # タイトル生成
            response = self.client.models.generate_content(
                model=self.title_model,
                contents=contents,
                config=title_config,
            )
            
            if not hasattr(response, 'text') or not response.text:
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

    def generate_meeting_title(self, text: str) -> str:
        """会議タイトルを生成する（互換性のため）
        
        Args:
            text (str): 会議の書き起こしテキスト
            
        Returns:
            str: 生成された会議タイトル
        """
        return self.generate_title(text)

    def summarize_minutes(self, text: str, system_prompt: str) -> str:
        """議事録のまとめを生成する
        
        Args:
            text (str): 要約する元のテキスト
            system_prompt (str): 議事録生成用のシステムプロンプト
            
        Returns:
            str: 生成された議事録のまとめ
            
        Raises:
            GeminiAPIError: 議事録生成に失敗した場合
        """
        try:
            # 議事録生成用の設定
            minutes_config = {
                "temperature": 1.0,
                "top_p": 0.95,
                "top_k": 64,
                "max_output_tokens": 8192,
                "response_mime_type": "text/plain",
            }
            
            # コンテンツ準備
            contents = [
                text,
                system_prompt
            ]
            
            logger.info(f"Generating minutes using {self.minutes_model}")
            
            # 議事録生成
            response = self.client.models.generate_content(
                model=self.minutes_model,
                contents=contents,
                config=minutes_config,
            )
            
            if not hasattr(response, 'text') or not response.text:
                raise GeminiAPIError("議事録生成からの応答が空です")
            
            logger.info(f"Generated minutes ({len(response.text)} characters)")
            return response.text
                
        except Exception as e:
            error_msg = f"議事録生成に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg) 