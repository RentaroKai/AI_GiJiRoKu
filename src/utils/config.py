#import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import sys
from .path_resolver import get_config_file_path

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """設定関連のエラーを扱うカスタム例外クラス"""
    pass

class OutputConfig(BaseModel):
    """出力設定モデル"""
    default_dir: str = "output"

class TranscriptionConfig(BaseModel):
    """文字起こし設定モデル"""
    method: str = "gemini"
    segment_length_seconds: int = 450
    enable_speaker_remapping: bool = True  # 話者置換処理を有効にするかどうか

class SummarizationConfig(BaseModel):
    """議事録生成設定モデル"""
    model: str = "gemini"  # デフォルト値はGemini

class ModelsConfig(BaseModel):
    """AIモデル名設定モデル"""
    gemini_transcription: str = "gemini-2.5-pro-exp-03-25"
    gemini_minutes: str = "gemini-2.5-pro-exp-03-25"
    gemini_title: str = "gemini-2.0-flash"
    openai_chat: str = "o3-mini-2025-01-31"
    openai_st: str = "gpt-4o"
    openai_sttitle: str = "gpt-4o-mini"
    openai_audio: str = "gpt-4o-mini-transcribe"
    openai_4oaudio: str = "gpt-4o-audio-preview"

class AppConfig(BaseModel):
    """アプリケーション設定モデル"""
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    output: OutputConfig = OutputConfig()
    debug_mode: bool = False
    log_level: str = "INFO"
    log_retention_days: int = 7
    max_audio_size_mb: int = 1024  # 1GB
    temp_file_retention_hours: int = 24
    transcription: TranscriptionConfig = TranscriptionConfig()
    summarization: SummarizationConfig = SummarizationConfig()
    models: ModelsConfig = ModelsConfig()

    class Config:
        arbitrary_types_allowed = True

class ConfigManager:
    def __init__(self, config_file: str = "settings.json"):
        # 実行モードの詳細なログ
        is_frozen = getattr(sys, 'frozen', False)
        logger.info(f"ConfigManager初期化: 実行モード={'PyInstaller' if is_frozen else '通常'}")
        
        # 統一されたパス解決ユーティリティを使用
        self.config_file = get_config_file_path(config_file)
        logger.info(f"設定ファイル絶対パス: {self.config_file.absolute()}")
        
        self.config = self._load_config()

    def _load_config(self) -> AppConfig:
        """設定ファイルの読み込み"""
        try:
            if self.config_file.exists():
                logger.info(f"設定ファイルを読み込みます: {self.config_file}")
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                logger.info("設定ファイルの読み込みに成功しました")
                
                # 文字起こし設定の詳細なログ
                transcription_method = config_data.get("transcription", {}).get("method", "gemini")
                logger.info(f"読み込まれた文字起こし方式: {transcription_method}")
                
                return AppConfig(**config_data)
            else:
                logger.warning(f"設定ファイルが見つかりません: {self.config_file}")
                logger.info("デフォルト設定を使用します")
                # デフォルト設定の詳細なログ
                default_config = AppConfig()
                logger.info(f"デフォルト文字起こし方式: {default_config.transcription.method}")
                return default_config
        except Exception as e:
            logger.error(f"設定ファイルの読み込み中にエラーが発生しました: {str(e)}")
            # デフォルト設定の詳細なログ
            default_config = AppConfig()
            logger.info(f"エラー後のデフォルト文字起こし方式: {default_config.transcription.method}")
            return default_config

    def save_config(self) -> None:
        """設定の保存"""
        try:
            config_dict = self.config.dict()
            logger.info(f"設定を保存します: {self.config_file.absolute()}")
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=4, ensure_ascii=False)
            logger.info("設定の保存に成功しました")
        except Exception as e:
            logger.error(f"設定の保存中にエラーが発生しました: {str(e)}")
            raise ConfigError(f"設定の保存に失敗しました: {str(e)}")

    def update_config(self, config_dict: Dict[str, Any]) -> None:
        """
        設定の更新
        Args:
            config_dict (Dict[str, Any]): 更新する設定のディクショナリ
        """
        try:
            # 出力設定の特別処理
            if "output" in config_dict:
                output_config = config_dict["output"]
                if isinstance(output_config, dict):
                    self.config.output = OutputConfig(**output_config)
                else:
                    logger.warning("Invalid output configuration format")
                del config_dict["output"]

            # 文字起こし設定の特別処理
            if "transcription" in config_dict:
                transcription_config = config_dict["transcription"]
                if isinstance(transcription_config, dict):
                    self.config.transcription = TranscriptionConfig(**transcription_config)
                else:
                    logger.warning("Invalid transcription configuration format")
                del config_dict["transcription"]

            # 議事録生成設定の特別処理
            if "summarization" in config_dict:
                summarization_config = config_dict["summarization"]
                if isinstance(summarization_config, dict):
                    self.config.summarization = SummarizationConfig(**summarization_config)
                else:
                    logger.warning("Invalid summarization configuration format")
                del config_dict["summarization"]

            # モデル設定の特別処理
            if "models" in config_dict:
                models_config_data = config_dict["models"]
                if isinstance(models_config_data, dict):
                    # 既存のモデル設定を読み込み、新しいデータで上書き
                    current_models_dict = self.config.models.dict()
                    current_models_dict.update(models_config_data)
                    self.config.models = ModelsConfig(**current_models_dict)
                else:
                    logger.warning("Invalid models configuration format")
                del config_dict["models"]

            # その他の設定を更新
            for key, value in config_dict.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                else:
                    logger.warning(f"Unknown configuration key: {key}")
            
            self.save_config()
            logger.info("Configuration updated successfully")
        except Exception as e:
            logger.error(f"Error updating configuration: {str(e)}")
            raise ConfigError(f"Failed to update configuration: {str(e)}")

    def get_config(self) -> AppConfig:
        """現在の設定を取得"""
        return self.config

    def get_model(self, model_type: str) -> str:
        """指定されたタイプのAIモデル名を取得する"""
        try:
            model_name = getattr(self.config.models, model_type, None)
            if model_name is None:
                # ModelsConfigのデフォルト値を使うため、エラーではなく警告ログに留める
                logger.warning(f"指定されたモデルタイプが見つかりません: {model_type}。ModelsConfigのデフォルト値を使用します。")
                # デフォルト値を取得するために再度getattrする（あるいはModelsConfigのデフォルトを直接参照）
                default_model_name = getattr(ModelsConfig(), model_type, "") # デフォルト取得失敗時は空文字
                if not default_model_name:
                     logger.error(f"ModelsConfigにもデフォルト値が見つかりません: {model_type}")
                return default_model_name
            return model_name
        except AttributeError:
            logger.error(f"'models' 設定オブジェクトが存在しません。デフォルト設定を確認してください。")
            return "" # エラー時は空文字を返すなど、適切なエラー処理を行う
        except Exception as e:
            logger.error(f"モデル名の取得中に予期せぬエラーが発生しました ({model_type}): {str(e)}")
            return "" # エラー時は空文字を返す

    def reset_to_defaults(self) -> None:
        """設定をデフォルトに戻す"""
        try:
            self.config = AppConfig()
            self.save_config()
            logger.info("Configuration reset to defaults")
        except Exception as e:
            logger.error(f"Error resetting configuration: {str(e)}")
            raise ConfigError(f"Failed to reset configuration: {str(e)}")

# グローバルなConfigManagerインスタンス
config_manager = ConfigManager() 