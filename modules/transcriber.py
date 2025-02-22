import os
import logging
from pathlib import Path
from src.services.gemini_transcription import GeminiTranscriptionService, TranscriptionError

logger = logging.getLogger(__name__)

class GeminiTranscriber:
    def __init__(self):
        """
        Gemini APIを使用した文字起こしクラスの初期化
        """
        logger.info("GeminiTranscriberを初期化中...")
        self.service = GeminiTranscriptionService()
        logger.info("GeminiTranscriberの初期化が完了しました")

    def transcribe_audio(self, audio_file_path):
        """
        音声ファイルを文字起こしする
        Args:
            audio_file_path (str): 音声ファイルのパス
        Returns:
            str: 文字起こし結果のテキスト
        """
        try:
            logger.info(f"文字起こしを開始: {audio_file_path}")
            
            # GeminiTranscriptionServiceを使用して文字起こし
            result = self.service.process_audio(Path(audio_file_path))
            
            # formatted_textを取得
            response_text = result.get("formatted_text", "")
            logger.debug(f"文字起こし結果の長さ: {len(response_text)} 文字")
            
            return response_text
            
        except Exception as e:
            logger.error(f"文字起こし処理でエラーが発生: {str(e)}", exc_info=True)
            raise TranscriptionError(f"文字起こし処理に失敗: {str(e)}")

    def save_transcription(self, transcription, output_file):
        """
        文字起こし結果をテキストファイルとして保存
        Args:
            transcription (str): 文字起こし結果のテキスト
            output_file (str): 出力ファイルパス
        """
        try:
            logger.info(f"文字起こし結果を保存: {output_file}")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcription)
            logger.info(f"文字起こし結果を保存しました: {output_file}")
        except Exception as e:
            logger.error(f"文字起こし結果の保存中にエラーが発生: {str(e)}", exc_info=True)
            raise 