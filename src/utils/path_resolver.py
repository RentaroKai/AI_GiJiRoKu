import os
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def get_app_config_dir() -> Path:
    """アプリケーションの設定ディレクトリを取得する
    
    Returns:
        Path: 設定ディレクトリのパス（PyInstaller実行時は実行ファイルのディレクトリ/config）
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller実行時は実行ファイルのディレクトリを使用
        config_dir = Path(sys.executable).parent / 'config'
        logger.info(f"PyInstaller実行モード: 設定ディレクトリ = {config_dir.absolute()}")
    else:
        # 通常実行時はプロジェクトルートディレクトリを使用
        config_dir = Path.cwd() / 'config'
        logger.info(f"通常実行モード: 設定ディレクトリ = {config_dir.absolute()}")
    
    # 設定ディレクトリが存在しない場合は作成
    config_dir.mkdir(parents=True, exist_ok=True)
    
    return config_dir

def get_config_file_path(filename: str = "settings.json") -> Path:
    """設定ファイルの完全パスを取得する
    
    Args:
        filename (str): 設定ファイル名
        
    Returns:
        Path: 設定ファイルの完全パス
    """
    config_path = get_app_config_dir() / filename
    logger.debug(f"設定ファイルパス: {config_path.absolute()}")
    return config_path

def resolve_resource_path(relative_path: str) -> Path:
    """リソースファイルの完全パスを取得する
    
    Args:
        relative_path (str): リソースの相対パス
        
    Returns:
        Path: リソースファイルの完全パス
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller実行時
        base_path = Path(sys._MEIPASS)
    else:
        # 通常実行時
        base_path = Path.cwd()
    
    resource_path = base_path / relative_path
    logger.debug(f"リソースパス: {resource_path.absolute()}")
    return resource_path 