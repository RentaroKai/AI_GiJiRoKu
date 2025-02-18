from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any

class TranscriptionError(Exception):
    """書き起こし処理中のエラーを表すカスタム例外"""
    pass

class TranscriptionService(ABC):
    """書き起こしサービスの基底クラス"""
    
    def __init__(self, output_dir: str = "output/transcriptions"):
        """Initialize transcription service
        
        Args:
            output_dir (str): Output directory for transcriptions
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def process_audio(self, audio_file: Path) -> Dict[str, Any]:
        """Process audio file and generate transcription
        
        Args:
            audio_file (Path): Path to the audio file
            
        Returns:
            Dict[str, Any]: Transcription results including file paths and metadata
        """
        pass
    
    def validate_audio(self, audio_file: Path) -> bool:
        """Validate audio file before processing
        
        Args:
            audio_file (Path): Path to the audio file
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not audio_file.exists():
            return False
        
        valid_extensions = {'.mp3', '.wav', '.m4a', '.mp4'}
        return audio_file.suffix.lower() in valid_extensions
    
    def cleanup(self):
        """Clean up any temporary files or resources"""
        pass 