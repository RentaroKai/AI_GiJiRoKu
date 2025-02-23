import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import httplib2

import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content

logger = logging.getLogger(__name__)

# デフォルトのモデル設定
DEFAULT_TRANSCRIPTION_MODEL = "gemini-2.0-flash"  # 書き起こし用のデフォルトモデル
DEFAULT_MINUTES_MODEL = "gemini-2.0-pro-exp-02-05"  # 議事録まとめ用のデフォルトモデル

class TranscriptionError(Exception):
    """書き起こし処理中のエラーを表すカスタム例外"""
    pass

class GeminiAPI:
    def __init__(self, api_key: str = "", transcription_model: str = DEFAULT_TRANSCRIPTION_MODEL, minutes_model: str = DEFAULT_MINUTES_MODEL):
        """Initialize Gemini API client

        Args:
            api_key (str): Gemini API key. 環境変数GOOGLE_API_KEYが優先されます。
            transcription_model (str): 書き起こし用のモデル名。デフォルトはDEFAULT_TRANSCRIPTION_MODEL
            minutes_model (str): 議事録まとめ用のモデル名。デフォルトはDEFAULT_MINUTES_MODEL
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

        # モデル名の設定
        self.transcription_model = transcription_model
        self.minutes_model = minutes_model
        logger.info(f"書き起こしモデル: {self.transcription_model}")
        logger.info(f"議事録まとめモデル: {self.minutes_model}")

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