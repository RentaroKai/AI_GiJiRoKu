import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional
import sys
from .path_resolver import get_config_file_path, resolve_resource_path

logger = logging.getLogger(__name__)

class PromptManager:
    """プロンプト管理クラス"""
    
    DEFAULT_PROMPTS = {
        "minutes": "src/prompts/minutes.txt",
        "transcription": "src/prompts/transcription.txt",
        "reflection": "src/prompts/reflection.txt",
        "speakerremap": "src/prompts/speakerremap.txt"
    }
    
    def __init__(self, config_file: str = "settings.json"):
        """
        プロンプト管理クラスの初期化
        
        Args:
            config_file (str): 設定ファイル名
        """
        # 実行環境に応じたリソースパス解決
        if getattr(sys, 'frozen', False):
            # PyInstaller実行時
            self.base_dir = Path(sys._MEIPASS)
        else:
            # 通常実行時
            self.base_dir = Path.cwd()
        
        # 統一されたパス解決ユーティリティを使用
        self.config_file = get_config_file_path(config_file)
        logger.info(f"PromptManager: 設定ファイルパス: {self.config_file.absolute()}")
        
    def get_prompt(self, prompt_type: str) -> str:
        """
        指定タイプのプロンプトを取得する
        
        Args:
            prompt_type (str): プロンプトタイプ（minutes, transcription, reflectionなど）
            
        Returns:
            str: プロンプトテキスト
        """
        try:
            # 設定ファイルからカスタムプロンプトを読み込む
            custom_prompt = self._get_custom_prompt(prompt_type)
            if custom_prompt:
                logger.info(f"カスタムプロンプトを使用します: {prompt_type}")
                return custom_prompt
            
            # デフォルトプロンプトを読み込む
            default_prompt = self.get_default_prompt(prompt_type)
            if default_prompt:
                logger.info(f"デフォルトプロンプトを使用します: {prompt_type}")
                return default_prompt
            
            logger.error(f"未対応のプロンプトタイプです: {prompt_type}")
            return ""
            
        except Exception as e:
            logger.error(f"プロンプト取得中にエラーが発生しました: {str(e)}")
            return ""
    
    def save_custom_prompt(self, prompt_type: str, prompt_text: str) -> bool:
        """
        カスタムプロンプトを保存する
        
        Args:
            prompt_type (str): プロンプトタイプ
            prompt_text (str): プロンプトテキスト
            
        Returns:
            bool: 保存成功フラグ
        """
        try:
            # 設定ファイルの読み込み
            config = self._load_config()
            
            # prompts セクションが存在しない場合は作成
            if "prompts" not in config:
                config["prompts"] = {}
            
            # プロンプトを保存
            config["prompts"][prompt_type] = prompt_text
            
            # 設定ファイルに書き込み
            logger.info(f"カスタムプロンプトを保存します: {self.config_file.absolute()}")
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
                
            logger.info(f"カスタムプロンプトを保存しました: {prompt_type}")
            return True
            
        except Exception as e:
            logger.error(f"カスタムプロンプト保存中にエラーが発生しました: {str(e)}")
            return False
    
    def reset_prompt(self, prompt_type: str) -> bool:
        """
        プロンプトをデフォルトに戻す
        
        Args:
            prompt_type (str): プロンプトタイプ
            
        Returns:
            bool: リセット成功フラグ
        """
        try:
            # 設定ファイルの読み込み
            config = self._load_config()
            
            # prompts セクションが存在し、対象プロンプトが含まれる場合は削除
            if "prompts" in config and prompt_type in config["prompts"]:
                del config["prompts"][prompt_type]
                
                # prompts セクションが空になった場合は削除
                if not config["prompts"]:
                    del config["prompts"]
                
                # 設定ファイルに書き込み
                logger.info(f"プロンプト設定をリセットします: {self.config_file.absolute()}")
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                
            logger.info(f"プロンプトをデフォルトにリセットしました: {prompt_type}")
            return True
            
        except Exception as e:
            logger.error(f"プロンプトリセット中にエラーが発生しました: {str(e)}")
            return False
    
    def get_default_prompt(self, prompt_type: str) -> str:
        """
        デフォルトプロンプトを取得する
        
        Args:
            prompt_type (str): プロンプトタイプ
            
        Returns:
            str: デフォルトプロンプトテキスト
        """
        try:
            if prompt_type in self.DEFAULT_PROMPTS:
                # 共通パス解決ユーティリティを使用
                prompt_path = resolve_resource_path(self.DEFAULT_PROMPTS[prompt_type])
                
                logger.debug(f"プロンプトタイプ: {prompt_type}")
                logger.debug(f"検索パス: {prompt_path}")
                logger.debug(f"パスが存在するか: {prompt_path.exists()}")
                
                if prompt_path.exists():
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        prompt = f.read().strip()
                    return prompt
            return ""
        except Exception as e:
            logger.error(f"デフォルトプロンプト取得中にエラーが発生しました: {str(e)}")
            return ""
    
    def _get_custom_prompt(self, prompt_type: str) -> Optional[str]:
        """
        カスタムプロンプトを設定ファイルから取得する
        
        Args:
            prompt_type (str): プロンプトタイプ
            
        Returns:
            Optional[str]: カスタムプロンプトテキスト（設定されていない場合はNone）
        """
        try:
            config = self._load_config()
            return config.get("prompts", {}).get(prompt_type)
        except Exception as e:
            logger.error(f"カスタムプロンプト取得中にエラーが発生しました: {str(e)}")
            return None
    
    def _load_config(self) -> Dict:
        """
        設定ファイルを読み込む
        
        Returns:
            Dict: 設定データ
        """
        try:
            logger.debug(f"設定ファイルを読み込みます: {self.config_file}")
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.debug(f"設定ファイルを読み込みました: {len(config)} 項目")
                return config
            logger.debug("設定ファイルが存在しないため、空の設定を返します")
            return {}
        except Exception as e:
            logger.error(f"設定ファイル読み込み中にエラーが発生しました: {str(e)}")
            return {}

# グローバルなPromptManagerインスタンス
prompt_manager = PromptManager() 