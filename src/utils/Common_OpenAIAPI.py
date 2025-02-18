import openai
import os
import base64
import requests
from typing import List, Dict, Any
from pydantic import BaseModel
import time
import logging
from pathlib import Path

# ロガーの設定
logger = logging.getLogger(__name__)

# 定数定義
DEFAULT_CHAT_MODEL = "gpt-4o"
DEFAULT_VISION_MODEL = "gpt-4o"
DEFAULT_AUDIO_MODEL = "whisper-1"
DEFAULT_4oAUDIO_MODEL = "gpt-4o-audio-preview"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = ""

class APIError(Exception):
    """API関連のエラーを扱うカスタム例外クラス"""
    pass

def setup_logging(log_level=logging.INFO):
    """ロギングの設定"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.setLevel(log_level)

def get_client():    
    if 'SSL_CERT_FILE' in os.environ:
        del os.environ['SSL_CERT_FILE']
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OpenAI API keyが環境変数に設定されていません")
        raise APIError("OpenAI API keyが環境変数に設定されていません")
    openai.api_key = api_key
    return openai.OpenAI()

def generate_chat_response(system_prompt, user_message_content, max_tokens=DEFAULT_MAX_TOKENS, temperature=DEFAULT_TEMPERATURE, model_name=DEFAULT_CHAT_MODEL):
    """チャットレスポンスを生成（リトライなし）"""
    client = get_client()
    try:
        params = {
            "model": model_name,
            "temperature": temperature,
            "messages": []
        }

        if system_prompt:
            params["messages"].append({"role": "system", "content": system_prompt})

        params["messages"].append({"role": "user", "content": user_message_content})

        if isinstance(max_tokens, int) and max_tokens > 0:
            params["max_tokens"] = max_tokens

        logger.info(f"チャットリクエストを送信: モデル={model_name}")
        response = client.chat.completions.create(**params)
        logger.info("チャットレスポンスを受信しました")
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"チャットレスポンス生成中にエラーが発生しました: {str(e)}")
        raise APIError(f"チャットレスポンスの生成に失敗しました: {str(e)}")

def generate_transcribe_from_audio(audio_file, model=DEFAULT_AUDIO_MODEL, language="ja", prompt=""):
    """音声からテキストを生成"""
    client = get_client()
    try:
        logger.info(f"音声の書き起こしを開始: モデル={model}")
        transcript = client.audio.transcriptions.create(
            file=audio_file,
            model=model,
            response_format="json",
            language=language,
            prompt=prompt,
        )
        logger.info("音声の書き起こしが完了しました")
        return transcript.text
    except Exception as e:
        logger.error(f"音声の書き起こし中にエラーが発生しました: {str(e)}")
        raise APIError(f"音声の書き起こしに失敗しました: {str(e)}")

# 初期設定
setup_logging() 