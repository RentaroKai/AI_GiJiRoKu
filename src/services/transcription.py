import os
import pathlib
import logging
import datetime
from typing import Dict, Any
from ..utils.Common_OpenAIAPI import generate_transcribe_from_audio, generate_chat_response, APIError
import sys

logger = logging.getLogger(__name__)

class TranscriptionError(Exception):
    """書き起こし処理関連のエラーを扱うカスタム例外クラス"""
    pass

class TranscriptionService:
    def __init__(self, output_dir: str = "output/transcriptions"):
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"出力ディレクトリを作成/確認: {self.output_dir}")
        
        # プロンプトの読み込み
        if getattr(sys, 'frozen', False):
            # PyInstallerで実行している場合
            base_path = pathlib.Path(sys._MEIPASS)
            prompt_path = base_path / "src/prompts/transcription.txt"
            logger.info(f"PyInstaller実行モード - プロンプトパス: {prompt_path}")
        else:
            # 通常の実行の場合
            prompt_path = pathlib.Path("src/prompts/transcription.txt")
            logger.info(f"通常実行モード - プロンプトパス: {prompt_path}")
        
        if not prompt_path.exists():
            logger.error(f"書き起こしプロンプトファイルが見つかりません: {prompt_path}")
            logger.error(f"現在のディレクトリ: {os.getcwd()}")
            logger.error(f"ディレクトリ内容: {list(prompt_path.parent.glob('**/*'))}")
            raise TranscriptionError(f"書き起こしプロンプトファイルが見つかりません: {prompt_path}")
        
        try:
            logger.info(f"プロンプトファイルを読み込み中: {prompt_path}")
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read().strip()
            logger.info(f"プロンプトファイルを読み込みました（長さ: {len(self.system_prompt)}文字）")
        except UnicodeDecodeError as e:
            logger.error(f"プロンプトファイルのエンコーディングエラー: {str(e)}")
            # UTF-8で失敗した場合、CP932で試行
            try:
                with open(prompt_path, "r", encoding="cp932") as f:
                    self.system_prompt = f.read().strip()
                logger.info(f"CP932エンコーディングでプロンプトファイルを読み込みました（長さ: {len(self.system_prompt)}文字）")
            except Exception as e2:
                logger.error(f"CP932でも読み込みに失敗: {str(e2)}")
                raise TranscriptionError(f"プロンプトファイルの読み込みに失敗しました: {str(e)} -> {str(e2)}")
        except Exception as e:
            logger.error(f"プロンプトファイルの読み込み中にエラー: {str(e)}")
            raise TranscriptionError(f"プロンプトファイルの読み込みに失敗しました: {str(e)}")

    def process_audio(self, audio_file: pathlib.Path, additional_prompt: str = "") -> Dict[str, Any]:
        """音声ファイルの書き起こし処理を実行"""
        try:
            logger.info(f"書き起こしを開始: {audio_file}")
            logger.info(f"音声ファイルサイズ: {audio_file.stat().st_size:,} bytes")
            
            # タイムスタンプの生成
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            logger.info(f"タイムスタンプ: {timestamp}")
            
            # 音声からテキストを生成
            logger.info("OpenAI APIで音声認識を開始")
            with open(audio_file, "rb") as f:
                transcription = generate_transcribe_from_audio(f)
            
            if not transcription:
                logger.error("音声認識の結果が空です")
                raise TranscriptionError("書き起こしの生成に失敗しました")
            
            logger.info(f"音声認識完了（テキスト長: {len(transcription)}文字）")
            
            # 生のテキストを保存
            raw_output_path = self.output_dir / f"transcription_{timestamp}.txt"
            logger.info(f"生テキストを保存: {raw_output_path}")
            try:
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write(transcription)
            except Exception as e:
                logger.error(f"生テキストの保存中にエラー: {str(e)}")
                raise TranscriptionError(f"生テキストの保存に失敗しました: {str(e)}")
            
            # GPT-4oで整形
            logger.info("GPT-4oでテキストの整形を開始")
            if additional_prompt:
                logger.info(f"追加プロンプトあり（長さ: {len(additional_prompt)}文字）")
            
            full_prompt = f"{additional_prompt}\n{transcription}" if additional_prompt else transcription
            formatted_text = generate_chat_response(self.system_prompt, full_prompt)
            
            if not formatted_text:
                logger.error("テキスト整形の結果が空です")
                raise TranscriptionError("テキストの整形に失敗しました")
            
            logger.info(f"テキスト整形完了（長さ: {len(formatted_text)}文字）")
            
            # 整形済みテキストを保存
            formatted_output_path = self.output_dir / f"transcription_summary_{timestamp}.txt"
            logger.info(f"整形済みテキストを保存: {formatted_output_path}")
            try:
                with open(formatted_output_path, "w", encoding="utf-8") as f:
                    f.write(formatted_text)
            except Exception as e:
                logger.error(f"整形済みテキストの保存中にエラー: {str(e)}")
                raise TranscriptionError(f"整形済みテキストの保存に失敗しました: {str(e)}")
            
            logger.info("書き起こし処理が完了しました")
            return {
                "raw_text": transcription,
                "formatted_text": formatted_text,
                "raw_file": raw_output_path,
                "formatted_file": formatted_output_path,
                "timestamp": timestamp
            }
            
        except APIError as e:
            logger.error(f"API処理中にエラーが発生しました: {str(e)}")
            raise TranscriptionError(f"APIエラー: {str(e)}")
        except Exception as e:
            logger.error(f"書き起こし処理中にエラーが発生しました: {str(e)}")
            logger.error(f"エラータイプ: {type(e).__name__}")
            raise TranscriptionError(f"書き起こしに失敗しました: {str(e)}")

    def get_output_path(self, timestamp: str = None) -> pathlib.Path:
        """出力ファイルパスの生成"""
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return self.output_dir / f"transcription_summary_{timestamp}.txt" 