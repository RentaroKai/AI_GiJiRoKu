import openai
import os
import base64
from typing import List, Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 定数定義
DEFAULT_CHAT_MODEL = "gpt-4o"
DEFAULT_ST_MODEL = "gpt-4o"
DEFAULT_STTITLE_MODEL = "gpt-4o-mini"
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
        import json
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