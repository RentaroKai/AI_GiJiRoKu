"""
Changes:
- スピーカーリマップ処理システムの初期実装
- 基底クラス SpeakerRemapperBase の実装
- OpenAI用の OpenAISpeakerRemapper クラスの実装
- Gemini用の GeminiSpeakerRemapper クラスの実装
- ファクトリー関数 create_speaker_remapper の実装
- config_managerからの設定取得方法を修正（2024-03-08追加）
Date: 2024-03-08
"""

import os
import logging
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, Union

from src.utils.Common_OpenAIAPI import generate_chat_response, APIError
from src.utils.gemini_api import GeminiAPI
from src.utils.config import config_manager
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class SpeakerRemapperBase:
    """スピーカーリマップ処理の基底クラス"""
    
    def __init__(self):
        """初期化"""
        self.prompt_manager = PromptManager()
    
    def get_remap_prompt(self) -> str:
        """話者リマッププロンプトを取得"""
        return self.prompt_manager.get_prompt("speakerremap")
    
    def process_transcript(self, transcript_file: Union[str, Path]) -> Path:
        """
        文字起こしファイルの話者名をリマップする
        
        Args:
            transcript_file (Union[str, Path]): 文字起こしファイルのパス
            
        Returns:
            Path: リマップ後のファイルパス
        """
        logger.info(f"話者リマップ処理を開始: {transcript_file}")
        
        # ファイルパスをPathオブジェクトに変換
        if isinstance(transcript_file, str):
            transcript_file = Path(transcript_file)
        
        # 文字起こしファイルの内容を読み込む
        with open(transcript_file, "r", encoding="utf-8") as f:
            transcript_text = f.read()
        
        # AIによる話者マッピングの取得
        speaker_mapping = self._get_speaker_mapping(transcript_text)
        logger.info(f"生成された話者マッピング: {speaker_mapping}")
        
        # 話者名の置換処理
        remapped_text = self._replace_speakers(transcript_text, speaker_mapping)
        
        # リマップ後のファイルを保存
        output_file = transcript_file.with_name(f"{transcript_file.stem}_remapped{transcript_file.suffix}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(remapped_text)
        
        logger.info(f"話者リマップ処理が完了しました。出力ファイル: {output_file}")
        return output_file
    
    def _get_speaker_mapping(self, transcript_text: str) -> Dict[str, str]:
        """
        AIを使用して話者マッピングを取得する
        
        Args:
            transcript_text (str): 文字起こしテキスト
            
        Returns:
            Dict[str, str]: 話者名マッピング辞書 (例: {"話者A": "山田"})
        """
        raise NotImplementedError("This method should be implemented by subclasses")
    
    def _replace_speakers(self, transcript_text: str, speaker_mapping: Dict[str, str]) -> str:
        """
        文字起こしテキスト内の話者名を置換する
        
        Args:
            transcript_text (str): 元の文字起こしテキスト
            speaker_mapping (Dict[str, str]): 話者名マッピング辞書
            
        Returns:
            str: 話者名が置換されたテキスト
        """
        result_text = transcript_text
        
        # JSON内の話者名を置換
        for old_name, new_name in speaker_mapping.items():
            # "speaker": "話者A" のようなパターンを探して置換
            pattern = f'"speaker"\\s*:\\s*"{re.escape(old_name)}"'
            replacement = f'"speaker": "{new_name}"'
            result_text = re.sub(pattern, replacement, result_text)
        
        return result_text
    
    def _parse_mapping_response(self, ai_response: str) -> Dict[str, str]:
        """
        AIからのレスポンスをパースして話者マッピング辞書を取得
        
        Args:
            ai_response (str): AIからのレスポンス
            
        Returns:
            Dict[str, str]: 話者名マッピング辞書
        """
        # JSONブロックを抽出
        json_match = re.search(r'```json\s*(.*?)\s*```', ai_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # ```jsonなしの場合、テキスト全体から{}で囲まれた部分を探す
            json_match = re.search(r'{.*}', ai_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.warning("JSONフォーマットが見つかりませんでした。レスポンス全体をJSONとして解析します。")
                json_str = ai_response
        
        try:
            # JSONパース
            mapping = json.loads(json_str)
            return mapping
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}\nレスポンス: {ai_response}")
            # 空の辞書を返す（エラー発生時）
            return {}


class OpenAISpeakerRemapper(SpeakerRemapperBase):
    """OpenAI APIを使用した話者リマッパー"""
    
    def _get_speaker_mapping(self, transcript_text: str) -> Dict[str, str]:
        """OpenAI APIを使用して話者マッピングを取得"""
        prompt = self.get_remap_prompt()
        
        try:
            # OpenAI APIでチャットレスポンスを生成
            response = generate_chat_response(
                system_prompt=prompt,
                user_message_content=transcript_text
            )
            
            # レスポンスから話者マッピングを抽出
            return self._parse_mapping_response(response)
            
        except APIError as e:
            logger.error(f"OpenAI API呼び出し中にエラーが発生: {e}")
            return {}


class GeminiSpeakerRemapper(SpeakerRemapperBase):
    """Gemini APIを使用した話者リマッパー"""
    
    def _get_speaker_mapping(self, transcript_text: str) -> Dict[str, str]:
        """Gemini APIを使用して話者マッピングを取得"""
        prompt = self.get_remap_prompt()
        
        try:
            # Gemini APIの初期化
            api = GeminiAPI()
            
            # Gemini APIを使用してプロンプトと文字起こしテキストを送信
            # 注意: summarize_minutesの引数順序は (text, system_prompt)
            response = api.summarize_minutes(
                text=transcript_text,
                system_prompt=prompt
            )
            
            # レスポンスから話者マッピングを抽出
            return self._parse_mapping_response(response)
            
        except Exception as e:
            logger.error(f"Gemini API呼び出し中にエラーが発生: {e}")
            return {}


def create_speaker_remapper() -> SpeakerRemapperBase:
    """
    設定に基づいて適切な話者リマッパーを作成する
    
    Returns:
        SpeakerRemapperBase: 話者リマッパーのインスタンス
    """
    # 設定からAIモデルタイプを取得
    ai_model = config_manager.get_config().transcription.method
    
    # 詳細なログ
    logger.info(f"話者リマッパー作成: 設定されたAIモデル={ai_model}")
    logger.info(f"話者リマッパー作成: config_manager={config_manager}")
    logger.info(f"話者リマッパー作成: 設定ファイルパス={config_manager.config_file}")
    
    # モデルタイプに応じてリマッパーを作成
    if ai_model == "gemini":
        logger.info("Gemini APIを使用した話者リマッパーを作成します")
        return GeminiSpeakerRemapper()
    else:
        logger.info(f"OpenAI APIを使用した話者リマッパーを作成します (AIモデル: {ai_model})")
        return OpenAISpeakerRemapper() 