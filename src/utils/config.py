#import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel
import sys

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

    class Config:
        arbitrary_types_allowed = True

class ConfigManager:
    def __init__(self, config_file: str = "config/settings.json"):
        # 実行モードの詳細なログ
        is_frozen = getattr(sys, 'frozen', False)
        logger.info(f"ConfigManager初期化: 実行モード={'PyInstaller' if is_frozen else '通常'}")
        
        self.config_file = Path(config_file)
        # 設定ファイルの絶対パスのログ
        logger.info(f"設定ファイル絶対パス: {self.config_file.absolute()}")
        
        # PyInstallerモードの場合、実行ファイルディレクトリ内の設定ファイルを優先
        if is_frozen:
            exe_dir = Path(sys.executable).parent
            alt_config_file = exe_dir / config_file
            logger.info(f"PyInstaller実行モードの代替設定ファイルパス: {alt_config_file}")
            
            if alt_config_file.exists():
                logger.info(f"PyInstaller実行モードで代替設定ファイルが見つかりました。こちらを使用します。")
                self.config_file = alt_config_file
        
        logger.info(f"最終的に使用する設定ファイル: {self.config_file}")
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
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
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=4, ensure_ascii=False)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            raise ConfigError(f"Failed to save configuration: {str(e)}")

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