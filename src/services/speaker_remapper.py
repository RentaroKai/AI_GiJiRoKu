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
        
        # テキストの基本情報をログに記録
        transcript_length = len(transcript_text)
        speaker_count = transcript_text.count('"speaker"')
        logger.info(f"変換対象の文字起こしファイル: 長さ={transcript_length}文字, 話者出現回数={speaker_count}回")
        
        # "speaker": パターンの出現をカウント
        speaker_pattern = r'"speaker"\s*:\s*"([^"]*)"'
        speakers = re.findall(speaker_pattern, transcript_text)
        unique_speakers = set(speakers)
        
        logger.info(f"変換前の一意な話者: {len(unique_speakers)}人 - {', '.join(sorted(unique_speakers))}")
        
        # AIによる話者マッピングの取得
        speaker_mapping = self._get_speaker_mapping(transcript_text)
        
        # マッピング結果を表形式で分かりやすく表示
        logger.info("【話者マッピング結果】")
        logger.info("┌─────────────────┬─────────────────┐")
        logger.info("│  元の話者名     │  マッピング後   │")
        logger.info("├─────────────────┼─────────────────┤")
        
        # 元の話者がマッピングに含まれているか確認
        mapped_speakers = set()
        for speaker in sorted(unique_speakers):
            mapped_to = speaker_mapping.get(speaker, "【変換なし】")
            mapped_speakers.add(mapped_to)
            logger.info(f"│ {speaker:<15} │ {mapped_to:<15} │")
        
        logger.info("└─────────────────┴─────────────────┘")
        
        # マッピングに含まれているが元のテキストに存在しない話者の警告
        for original in speaker_mapping:
            if original not in unique_speakers:
                logger.warning(f"警告: マッピングには「{original}」が含まれていますが、元のテキストには存在しません")
        
        # 話者名の置換処理
        remapped_text = self._replace_speakers(transcript_text, speaker_mapping)
        
        # 変換後の話者情報をログ
        after_speakers = re.findall(speaker_pattern, remapped_text)
        after_unique_speakers = set(after_speakers)
        
        # 変換結果の概要を表示
        logger.info(f"変換後の一意な話者: {len(after_unique_speakers)}人 - {', '.join(sorted(after_unique_speakers))}")
        
        # 変換前後の一致確認（マッピング後の予想話者と実際の話者を比較）
        if mapped_speakers != after_unique_speakers:
            logger.warning("警告: マッピング後の予想話者と実際の話者が一致しません")
            missing = mapped_speakers - after_unique_speakers
            if missing:
                logger.warning(f"マッピングで期待されたが存在しない話者: {', '.join(missing)}")
            extra = after_unique_speakers - mapped_speakers
            if extra:
                logger.warning(f"マッピングになかったが存在する話者: {', '.join(extra)}")
        
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
        
        # 詳細なログ出力のために全体のマッピングをログに記録
        logger.info(f"話者リマップ開始: 以下のマッピングを適用します:")
        for old_name, new_name in speaker_mapping.items():
            logger.info(f"  - \"{old_name}\" → \"{new_name}\"")
        
        # 変換カウントを記録する辞書
        replacement_counts = {old: 0 for old in speaker_mapping.keys()}
        
        # JSON内の話者名を置換
        for old_name, new_name in speaker_mapping.items():
            # "speaker": "話者A" のようなパターンを探して置換
            pattern = f'"speaker"\\s*:\\s*"{re.escape(old_name)}"'
            replacement = f'"speaker": "{new_name}"'
            
            # 置換前のテキストを保存
            before_text = result_text
            
            # 置換実行
            result_text = re.sub(pattern, replacement, result_text)
            
            # 置換回数を計算
            count = before_text.count(f'"speaker": "{old_name}"')
            actual_count = before_text.count(f'"speaker": "{old_name}"') - result_text.count(f'"speaker": "{old_name}"')
            replacement_counts[old_name] = actual_count
            
            logger.info(f"  話者置換: \"{old_name}\" → \"{new_name}\"、{actual_count}件の置換 (検出: {count}件)")
        
        # 全体の置換結果サマリーをログに記録
        total_replacements = sum(replacement_counts.values())
        logger.info(f"話者リマップ完了: 合計{total_replacements}件の置換を実行しました")
        
        # マッピングはあるが置換されなかった話者を警告
        for old_name, count in replacement_counts.items():
            if count == 0:
                logger.warning(f"警告: 話者「{old_name}」は定義されていますが、テキスト内での置換はありませんでした")
        
        return result_text
    
    def _parse_mapping_response(self, ai_response: str) -> Dict[str, str]:
        """
        AIからのレスポンスをパースして話者マッピング辞書を取得
        
        Args:
            ai_response (str): AIからのレスポンス
            
        Returns:
            Dict[str, str]: 話者名マッピング辞書
        """
        # 処理前のAIレスポンスをログに残す（機密情報がない範囲で）
        logger.info(f"AIレスポンスの解析を開始します (長さ: {len(ai_response)}文字)")
        
        # レスポンスの一部をログに残す（デバッグ用）
        if len(ai_response) > 300:
            logger.debug(f"AIレスポンス (先頭300文字): {ai_response[:300]}...")
        else:
            logger.debug(f"AIレスポンス全体: {ai_response}")
        
        # JSONブロックを抽出
        json_match = re.search(r'```json\s*(.*?)\s*```', ai_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            logger.info("```json```ブロックからJSONを抽出しました")
        else:
            # ```jsonなしの場合、テキスト全体から{}で囲まれた部分を探す
            json_match = re.search(r'{.*}', ai_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                logger.info("{}で囲まれたJSON形式のテキストを抽出しました")
            else:
                logger.warning("JSONフォーマットが見つかりませんでした。レスポンス全体をJSONとして解析します。")
                json_str = ai_response
        
        # JSONデータをログに記録（デバッグ用）
        logger.debug(f"解析するJSONデータ: {json_str}")
        
        try:
            # JSONパース
            mapping = json.loads(json_str)
            
            # マッピングの内容を詳細にログに記録
            logger.info(f"抽出された話者マッピング ({len(mapping)}件):")
            for original, remapped in mapping.items():
                logger.info(f"  - \"{original}\" → \"{remapped}\"")
            
            # 同じ話者名にマッピングされているケースを検出して警告
            value_counts = {}
            for v in mapping.values():
                value_counts[v] = value_counts.get(v, 0) + 1
            
            # 重複マッピングがある場合は強調して警告
            duplicates_found = False
            for value, count in value_counts.items():
                if count > 1:
                    duplicates_found = True
                    duplicated = [k for k, v in mapping.items() if v == value]
                    logger.warning(f"⚠⚠⚠ 警告: {count}人の話者が同じ名前「{value}」にマッピングされています: {', '.join(duplicated)}")
            
            if duplicates_found:
                logger.warning("複数の話者が同じ名前にマッピングされています。これは全員同じ話者に変換されることを意味します。")
                logger.warning("プロンプトを修正するか、手動でマッピングを調整することをお勧めします。")
            
            # マッピングの値が空の場合も警告
            empty_mappings = [k for k, v in mapping.items() if not v]
            if empty_mappings:
                logger.warning(f"警告: 以下の話者は空の値にマッピングされています: {', '.join(empty_mappings)}")
            
            return mapping
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            logger.error(f"解析に失敗したJSON文字列: {json_str}")
            # エラーの詳細を表示
            logger.error(f"エラー位置: {e.pos}, 行: {e.lineno}, 列: {e.colno}")
            logger.error(f"エラー前後の文字列: {json_str[max(0, e.pos-20):min(len(json_str), e.pos+20)]}")
            
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