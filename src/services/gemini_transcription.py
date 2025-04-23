import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from src.utils.new_gemini_api import GeminiAPI, GeminiAPIError as TranscriptionError
from src.services.base_transcription import TranscriptionService

logger = logging.getLogger(__name__)

class GeminiTranscriptionService(TranscriptionService):
    """Gemini APIを使用した書き起こしサービス"""
    
    def __init__(self, output_dir: str = "output/transcriptions", config_path: str = "config/settings.json"):
        """Initialize the Gemini transcription service
        
        Args:
            output_dir (str): Output directory for transcriptions
            config_path (str): Path to the configuration file
        """
        super().__init__(output_dir)
        self.config_path = config_path
        self.api_key = self._load_api_key()
        self.gemini_api = GeminiAPI(api_key=self.api_key)
        self.system_prompt = self._load_system_prompt()
    
    def _load_api_key(self) -> str:
        """Load Gemini API key from configuration"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            api_key = config.get('gemini_api_key')
            if not api_key:
                raise TranscriptionError("Gemini API key not found in configuration")
            
            return api_key
        except Exception as e:
            logger.error(f"Failed to load API key: {str(e)}")
            raise TranscriptionError(f"Failed to load API key: {str(e)}")
    
    def _load_system_prompt(self) -> str:
        """Load system prompt for transcription"""
        try:
            prompt_path = Path("src/prompts/transcriptionGEMINI.txt")
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to load system prompt: {str(e)}")
            raise TranscriptionError(f"Failed to load system prompt: {str(e)}")
    
    def process_audio(self, audio_file: Path) -> Dict[str, Any]:
        """Process audio file and generate transcription
        
        Args:
            audio_file (Path): Path to the audio file
            
        Returns:
            Dict[str, Any]: Transcription results including file paths and metadata
        """
        try:
            logger.info(f"Starting transcription for: {audio_file}")
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            
            # Transcribe using Gemini API
            result = self.gemini_api.transcribe_audio(audio_file, self.system_prompt)
            
            if not result["success"]:
                raise TranscriptionError(f"Transcription failed: {result['error']}")
            
            formatted_text = result["text"]
            
            # Save formatted text
            formatted_output_path = Path(self.output_dir) / f"transcription_summary_{timestamp}.txt"
            formatted_output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(formatted_output_path, "w", encoding="utf-8") as f:
                f.write(formatted_text)
            
            return {
                "raw_text": "",  # Gemini方式では生テキストは生成されない
                "formatted_text": formatted_text,
                "raw_file": None,
                "formatted_file": formatted_output_path,
                "timestamp": timestamp
            }
            
        except Exception as e:
            logger.error(f"Transcription processing failed: {str(e)}")
            raise TranscriptionError(f"Transcription processing failed: {str(e)}")
    
    def validate_audio(self, audio_file: Path) -> bool:
        """Validate audio file before processing
        
        Args:
            audio_file (Path): Path to the audio file
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not audio_file.exists():
            logger.error(f"Audio file not found: {audio_file}")
            return False
        
        # Check file extension
        valid_extensions = {'.mp3', '.wav', '.m4a', '.mp4'}
        if audio_file.suffix.lower() not in valid_extensions:
            logger.error(f"Unsupported audio format: {audio_file.suffix}")
            return False
        
        return True 

    def _process_with_gemini(self, audio_file: Path, timestamp: str) -> Dict[str, Any]:
        """Gemini方式での書き起こし処理"""
        logger.info("Geminiで音声認識・整形を開始")
        
        try:
            # 音声ファイルを文字列に変換 (互換性のため transcribe_audio を使用)
            formatted_text = self.gemini_api.transcribe_audio(str(audio_file))
            
            if not formatted_text:
                logger.error("音声認識・整形の結果が空です")
                raise TranscriptionError("書き起こしの生成に失敗しました")
            
            logger.info(f"音声認識・整形完了（テキスト長: {len(formatted_text)}文字）")
            
            # 整形済みテキストを保存
            formatted_output_path = Path(self.output_dir) / f"transcription_summary_{timestamp}.txt"
            formatted_output_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                with open(formatted_output_path, "w", encoding="utf-8") as f:
                    f.write(formatted_text)
            except Exception as e:
                logger.error(f"整形済みテキストの保存中にエラー: {str(e)}")
                raise TranscriptionError(f"整形済みテキストの保存に失敗しました: {str(e)}")
            
            logger.info("Gemini方式での書き起こし処理が完了しました")
            return {
                "raw_text": "",  # Gemini方式では生テキストは生成されない
                "formatted_text": formatted_text,
                "raw_file": None,
                "formatted_file": formatted_output_path,
                "timestamp": timestamp
            }
            
        except Exception as e:
            logger.error(f"Gemini方式での処理中にエラー: {str(e)}")
            raise TranscriptionError(f"Gemini方式での処理に失敗しました: {str(e)}") 