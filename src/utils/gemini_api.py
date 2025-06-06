import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import httplib2
import json
import time

import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from ..utils.config import config_manager
# from ..services.result_classes import TranscriptionResult, Segment # ModuleNotFoundErrorのためコメントアウト

logger = logging.getLogger(__name__)

# デフォルトのモデル設定
DEFAULT_TRANSCRIPTION_MODEL = config_manager.get_model("gemini_transcription")
DEFAULT_MINUTES_MODEL = config_manager.get_model("gemini_minutes")
DEFAULT_TITLE_MODEL = config_manager.get_model("gemini_title")

MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒

class TranscriptionError(Exception):
    """書き起こし処理中のエラーを表すカスタム例外"""
    pass

class GeminiAPI:
    def __init__(self, transcription_model: str = DEFAULT_TRANSCRIPTION_MODEL, minutes_model: str = DEFAULT_MINUTES_MODEL, title_model: str = DEFAULT_TITLE_MODEL):
        """Initialize Gemini API client

        Args:
            transcription_model (str): 書き起こし用のモデル名。デフォルトはDEFAULT_TRANSCRIPTION_MODEL
            minutes_model (str): 議事録まとめ用のモデル名。デフォルトはDEFAULT_MINUTES_MODEL
            title_model (str): タイトル生成用のモデル名。デフォルトはDEFAULT_TITLE_MODEL
        """
        # SSL証明書の設定
        cert_path = os.environ.get('SSL_CERT_FILE')
        if cert_path:
            httplib2.CA_CERTS = cert_path
            logger.info(f"SSL証明書が設定されました: {cert_path}")

        # 環境変数を優先、なければ設定ファイルからAPIキーを取得
        config = config_manager.get_config()
        self.api_key = os.getenv("GOOGLE_API_KEY") or config.gemini_api_key

        if not self.api_key:
            error_msg = "Gemini API keyが設定されていません。環境変数GOOGLE_API_KEYまたは設定ファイルのgemini_api_keyを設定してください。"
            logger.error(error_msg)
            raise TranscriptionError(error_msg)
        else:
            logger.info("Gemini API keyが設定されています")
            genai.configure(
                api_key=self.api_key,
                transport='rest'  # RESTトランスポートを指定
            )

        # Generation config from sample/gemini.py
        self.generation_config = {
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }

        # タイトル生成用の設定
        self.title_generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_schema": content.Schema(
                type=content.Type.OBJECT,
                enum=[],
                required=["title"],
                properties={
                    "title": content.Schema(
                        type=content.Type.STRING,
                    ),
                },
            ),
            "response_mime_type": "application/json",
        }

        # 議事録生成用の設定
        self.minutes_generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
        }

        # System prompt for transcription
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

        # モデル名の設定
        self.transcription_model = transcription_model
        self.minutes_model = minutes_model
        self.title_model = title_model
        logger.info(f"書き起こしモデル: {self.transcription_model}")
        logger.info(f"議事録まとめモデル: {self.minutes_model}")
        logger.info(f"タイトル生成モデル: {self.title_model}")

    def upload_file(self, file_path: str, mime_type: Optional[str] = None) -> Any:
        """Upload a file to Gemini API

        Args:
            file_path (str): Path to the file
            mime_type (str, optional): MIME type of the file

        Returns:
            Any: Uploaded file object
        """
        try:
            file = genai.upload_file(file_path, mime_type=mime_type)
            logger.info(f"Uploaded file '{file.display_name}' as: {file.uri}")
            return file
        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
            raise

    def transcribe_audio(self, audio_file_path: str) -> str:
        """音声ファイルを文字起こしする"""
        # API keyのチェックを最初に行う
        if not self.api_key:
            raise TranscriptionError("Gemini API keyが設定されていません")

        try:
            # 音声ファイルの存在チェック
            if not os.path.exists(audio_file_path):
                raise TranscriptionError(f"音声ファイルが見つかりません: {audio_file_path}")

            # モデルの初期化
            model = genai.GenerativeModel(
                model_name=self.transcription_model,
                generation_config=self.generation_config,
                system_instruction=self.system_prompt
            )

            # 音声ファイルをアップロード
            file = genai.upload_file(audio_file_path, mime_type="audio/mpeg")
            logger.info(f"Uploaded file '{file.display_name}' as: {file.uri}")

            try:
                # 直接generate_contentを使用し、タイムアウトを設定
                response = model.generate_content(
                    [file, "Take minutes of the meeting."],
                    generation_config=self.generation_config,
                    request_options={"timeout": 120}
                )

                if not response.text:
                    raise TranscriptionError("Gemini APIからの応答が空です")

                return response.text

            finally:
                # アップロードしたファイルの削除を試みる
                try:
                    file.delete()
                except Exception as e:
                    logger.warning(f"アップロードファイルの削除に失敗しました: {str(e)}")

        except TranscriptionError:
            raise
        except Exception as e:
            raise TranscriptionError(f"Gemini APIの処理に失敗しました: {str(e)}")

    def summarize_minutes(self, text: str, system_prompt: str) -> str:
        """議事録のまとめを生成する

        Args:
            text (str): 要約する元のテキスト
            system_prompt (str): 議事録生成用のシステムプロンプト

        Returns:
            str: 生成された議事録のまとめ
        """
        if not self.api_key:
            raise TranscriptionError("Gemini API keyが設定されていません")

        try:
            # モデルの初期化
            model = genai.GenerativeModel(
                model_name=self.minutes_model,
                generation_config=self.minutes_generation_config,
                system_instruction=system_prompt
            )

            logger.info("議事録まとめの生成を開始します")
            
            # チャットセッションの開始
            chat = model.start_chat()
            
            # 応答の生成
            response = chat.send_message(text)

            if not response.text:
                raise TranscriptionError("Gemini APIからの応答が空です")

            logger.info(f"議事録まとめを生成しました（{len(response.text)}文字）")
            return response.text

        except Exception as e:
            error_msg = f"議事録まとめの生成に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise TranscriptionError(error_msg)

    def generate_meeting_title(self, text: str) -> str:
        """会議タイトルを生成する

        Args:
            text (str): 会議の書き起こしテキスト

        Returns:
            str: 生成された会議タイトル

        Raises:
            TranscriptionError: タイトル生成に失敗した場合
        """
        if not self.api_key:
            raise TranscriptionError("Gemini API keyが設定されていません")

        try:
            # モデルの初期化
            model = genai.GenerativeModel(
                model_name=self.title_model,
                generation_config=self.title_generation_config,
                system_instruction=self.title_system_prompt
            )

            logger.info("会議タイトルの生成を開始します")
            
            # チャットセッションの開始
            chat = model.start_chat()
            
            # 応答の生成
            response = chat.send_message(text)

            if not response.text:
                raise TranscriptionError("Gemini APIからの応答が空です")

            try:
                # JSONとしてパース
                response_json = json.loads(response.text)
                title = response_json.get("title", "").strip()
                
                if not title:
                    raise TranscriptionError("生成されたタイトルが空です")
                
                logger.info(f"会議タイトルを生成しました: {title}")
                return title
                
            except json.JSONDecodeError as e:
                raise TranscriptionError(f"Gemini APIからの応答をJSONとしてパースできません: {str(e)}")

        except Exception as e:
            error_msg = f"会議タイトルの生成に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise TranscriptionError(error_msg)