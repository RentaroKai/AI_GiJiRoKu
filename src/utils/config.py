import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """設定関連のエラーを扱うカスタム例外クラス"""
    pass

class OutputConfig(BaseModel):
    """出力設定モデル"""
    default_dir: str = "output"

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

    class Config:
        arbitrary_types_allowed = True

class ConfigManager:
    def __init__(self, config_file: str = "config/settings.json"):
        self.config_file = Path(config_file)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config = self._load_config()

    def _load_config(self) -> AppConfig:
        """設定ファイルの読み込み"""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                logger.info("Configuration loaded successfully")
                return AppConfig(**config_data)
            else:
                logger.info("No configuration file found, using defaults")
                return AppConfig()
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return AppConfig()

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