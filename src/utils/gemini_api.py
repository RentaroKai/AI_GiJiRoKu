import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import httplib2

import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content

logger = logging.getLogger(__name__)

class TranscriptionError(Exception):
    """書き起こし処理中のエラーを表すカスタム例外"""
    pass

class GeminiAPI:
    def __init__(self, api_key: str = ""):
        """Initialize Gemini API client

        Args:
            api_key (str): Gemini API key. 環境変数GOOGLE_API_KEYが優先されます。
        """
        # SSL証明書の設定
        cert_path = os.environ.get('SSL_CERT_FILE')
        if cert_path:
            httplib2.CA_CERTS = cert_path
            logger.info(f"SSL証明書が設定されました: {cert_path}")

        # 環境変数を優先、なければ引数のapi_keyを使用
        self.api_key = os.getenv("GOOGLE_API_KEY") or api_key

        if not self.api_key:
            logger.warning("Gemini API keyが設定されていません")
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
            "response_schema": content.Schema(
                type=content.Type.OBJECT,
                enum=[],
                required=["conversations"],
                properties={
                    "conversations": content.Schema(
                        type=content.Type.ARRAY,
                        description="会話の記録の配列",
                        items=content.Schema(
                            type=content.Type.OBJECT,
                            enum=[],
                            required=["speaker", "utterance"],
                            properties={
                                "speaker": content.Schema(
                                    type=content.Type.STRING,
                                    description="発言者の名前や役職",
                                ),
                                "utterance": content.Schema(
                                    type=content.Type.STRING,
                                    description="発言内容",
                                ),
                            },
                        ),
                    ),
                },
            ),
            "response_mime_type": "application/json",
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

            # モデルの初期化　いったん古いやつでもいけるのか確かめる
            # model = genai.GenerativeModel('gemini-2.0-flash')
            # モデルの初期化
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                #model_name="gemini-2.0-pro-exp-02-05",
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