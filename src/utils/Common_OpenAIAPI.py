import openai
import os
import base64
from typing import List, Dict, Any
import logging
from pathlib import Path
from .config import config_manager
import json
from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError

logger = logging.getLogger(__name__)

# 定数定義
DEFAULT_CHAT_MODEL = config_manager.get_model("openai_chat")
DEFAULT_ST_MODEL = config_manager.get_model("openai_st")
DEFAULT_STTITLE_MODEL = config_manager.get_model("openai_sttitle")
DEFAULT_AUDIO_MODEL = config_manager.get_model("openai_audio")
DEFAULT_4oAUDIO_MODEL = config_manager.get_model("openai_4oaudio")
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
    """
    OpenAI APIクライアントを取得する
    
    環境変数 OPENAI_API_KEY からAPIキーを取得
    環境変数に設定されていない場合は設定ファイルから取得
    どちらにも存在しない場合はエラーを発生
    
    Returns:
        openai.OpenAI: OpenAI APIクライアント
    
    Raises:
        APIError: APIキーが見つからない場合
    """
    if 'SSL_CERT_FILE' in os.environ:
        del os.environ['SSL_CERT_FILE']
    
    # 1. 環境変数からAPIキーを取得
    api_key = os.getenv("OPENAI_API_KEY")
    
    # 2. 環境変数にない場合は設定ファイルから取得
    if not api_key:
        logger.info("環境変数にOpenAI API keyが設定されていないため、設定ファイルから取得します")
        try:
            api_key = config_manager.get_config().openai_api_key
            if api_key:
                logger.info("設定ファイルからOpenAI API keyを取得しました")
            else:
                logger.error("設定ファイルにもOpenAI API keyが設定されていません")
        except Exception as e:
            logger.error(f"設定ファイルからのOpenAI API key取得中にエラーが発生: {str(e)}")
    
    # 3. どちらにも存在しない場合はエラーを発生
    if not api_key:
        error_msg = "OpenAI API keyが環境変数にも設定ファイルにも設定されていません"
        logger.error(error_msg)
        raise APIError(error_msg)
    
    openai.api_key = api_key
    return openai.OpenAI()

def generate_chat_response(system_prompt, user_message_content, max_tokens=DEFAULT_MAX_TOKENS, temperature=DEFAULT_TEMPERATURE, model_name=DEFAULT_CHAT_MODEL):
    """チャットレスポンスを生成（リトライなし）
    
    もしもモデル名に"o3-mini"が含まれている場合は、o3mini向けのパラメータ形式でリクエストします。
    """
    client = get_client()
    try:
        # o3miniの場合（例: "o3-mini-2025-01-31"など）
        if "o3-mini" in model_name.lower():
            params = {
                "model": model_name,
                "messages": [],
                "response_format": {"type": "text"},
                "reasoning_effort": "high"
            }
            if system_prompt:
                params["messages"].append({
                    "role": "system",
                    "content": [
                        {"type": "text", "text": system_prompt}
                    ]
                })
            params["messages"].append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_message_content}
                ]
            })
            logger.info(f"o3mini チャットリクエストを送信: モデル={model_name}")
            response = client.chat.completions.create(**params)
            logger.info("o3mini チャットレスポンスを受信しました")
            return response.choices[0].message.content
        else:
            # 従来のモデルの処理
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

def generate_audio_chat_response(audio_file_path, system_prompt, temperature=DEFAULT_TEMPERATURE, model_name=DEFAULT_4oAUDIO_MODEL, max_tokens=2048):
    """
    音声ファイルとシステムプロンプトを使用してGPT-4 with audioモデルからレスポンスを生成する

    Args:
        audio_file_path (str): 処理する音声ファイルのパス
        system_prompt (str): システムプロンプト
        temperature (float): 生成時の温度パラメータ
        model_name (str): 使用するモデル名
        max_tokens (int): 最大トークン数

    Returns:
        str: モデルからの応答テキスト
    """
    client = get_client()
    try:
        with open(audio_file_path, "rb") as audio_file:
            logger.info(f"音声チャットリクエストを送信: モデル={model_name}")

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": [{"type": "text", "text": system_prompt}]
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": ""},
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": base64.b64encode(audio_file.read()).decode('utf-8'),
                                    "format": audio_file_path.split('.')[-1].lower()
                                }
                            }
                        ]
                    }
                ],
                modalities=["text"],
                response_format={"type": "text"},
                temperature=temperature,
                max_completion_tokens=max_tokens,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )

            logger.info("音声チャットレスポンスを受信しました")
            return response.choices[0].message.content

    except Exception as e:
        logger.error(f"音声チャットレスポンス生成中にエラーが発生しました: {str(e)}")
        raise APIError(f"音声チャットレスポンスの生成に失敗しました: {str(e)}")

def generate_structured_chat_response(system_prompt: str, user_message_content: str, json_schema: dict,
                                   temperature=DEFAULT_TEMPERATURE, model_name=DEFAULT_ST_MODEL):
    """構造化されたJSONレスポンスを生成する関数
    Args:
        system_prompt (str): システムプロンプト
        user_message_content (str): ユーザーメッセージ
        json_schema (dict): 期待するJSONスキーマ
        temperature (float): 生成時の温度パラメータ
        model_name (str): 使用するモデル名
    Returns:
        dict: スキーマに従った構造化されたレスポンス
    """
    client = get_client()
    try:
        params = {
            "model": model_name,
            "temperature": temperature,
            "messages": [],
            "response_format": {
                "type": "json_schema",
                "json_schema": json_schema
            }
        }

        if system_prompt:
            params["messages"].append({
                "role": "system",
                "content": [{"type": "text", "text": system_prompt}]
            })

        params["messages"].append({
            "role": "user",
            "content": [{"type": "text", "text": user_message_content}]
        })

        logger.info(f"構造化チャットリクエストを送信: モデル={model_name}")
        response = client.chat.completions.create(**params)
        logger.info("構造化チャットレスポンスを受信しました")
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"構造化チャットレスポンス生成中にエラーが発生しました: {str(e)}")
        raise APIError(f"構造化チャットレスポンスの生成に失敗しました: {str(e)}")

# 会議書き起こし用のスキーマ定義
MEETING_TRANSCRIPT_SCHEMA = {
    "name": "meeting_transcript",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "conversations": {
                "type": "array",
                "description": "会議での発言のリスト",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {
                            "type": "string",
                            "description": "発言者名"
                        },
                        "utterance": {
                            "type": "string",
                            "description": "発言内容"
                        }
                    },
                    "required": ["speaker", "utterance"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["conversations"],
        "additionalProperties": False
    }
}

# Added meeting title schema for title generation
MEETING_TITLE_SCHEMA = {
    "name": "meeting_title",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The title of the meeting."
            }
        },
        "required": ["title"],
        "additionalProperties": False
    }
}

def generate_meeting_title(transcript_text: str, temperature=DEFAULT_TEMPERATURE, model_name=DEFAULT_STTITLE_MODEL) -> str:
    """Generate the meeting title from the transcript text using a structured chat response."""
    system_prompt = "会議の書き起こしからこの会議のメインとなる議題が何だったのかを教えて。例：取引先とカフェの方向性に関する会議"
    response = generate_structured_chat_response(system_prompt=system_prompt, user_message_content=transcript_text, json_schema=MEETING_TITLE_SCHEMA, temperature=temperature, model_name=model_name)
    try:
        response_json = json.loads(response)
        meeting_title = response_json.get("title", "").strip()
        logger.info(f"Generated meeting title: {meeting_title}")
        return meeting_title
    except Exception as e:
        logger.error(f"Failed to parse meeting title response: {str(e)}")
        raise e
# system_prompt = """あなたは会議の書き起こしを行う専門家です。
# 音声ファイルに忠実な書き起こしテキストを作成してください。"""
# response = generate_structured_chat_response(
#     system_prompt=system_prompt,
#     user_message_content="会議の内容",
#     json_schema=MEETING_TRANSCRIPT_SCHEMA
# )

# 初期設定
setup_logging()