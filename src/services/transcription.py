import os
import pathlib
import logging
import datetime
import json
from typing import Dict, Any, Literal
from ..utils.Common_OpenAIAPI import generate_transcribe_from_audio, generate_chat_response, generate_audio_chat_response, APIError
import sys

logger = logging.getLogger(__name__)

class TranscriptionError(Exception):
    """書き起こし処理関連のエラーを扱うカスタム例外クラス"""
    pass

class TranscriptionService:
    def __init__(self, output_dir: str = "output/transcriptions", config_path: str = "config/transcription_config.json"):
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"出力ディレクトリを作成/確認: {self.output_dir}")
        
        # 設定の読み込み
        self.transcription_method = self._load_config(config_path)
        logger.info(f"書き起こし方式: {self.transcription_method}")
        
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

    def _load_config(self, config_path: str) -> Literal["whisper_gpt4", "gpt4_audio"]:
        """設定ファイルから書き起こし方式を読み込む"""
        try:
            config_file = pathlib.Path(config_path)
            if not config_file.exists():
                logger.info("設定ファイルが見つかりません。デフォルトの書き起こし方式を使用します。")
                return "gpt4_audio"
            
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config_text = f.read().strip()
                    # 空ファイルチェック
                    if not config_text:
                        logger.warning("設定ファイルが空です。デフォルトの書き起こし方式を使用します。")
                        return "gpt4_audio"
                    
                    # 文字列を整形して余分な文字を削除
                    config_text = config_text.replace('\n', '').replace('\r', '').strip()
                    # 最後のカンマを削除（一般的なJSON解析エラーの原因）
                    if config_text.endswith(',}'):
                        config_text = config_text[:-2] + '}'
                    
                    config = json.loads(config_text)
            except json.JSONDecodeError as e:
                logger.warning(f"設定ファイルのJSONパースに失敗しました: {str(e)}。デフォルトの書き起こし方式を使用します。")
                return "gpt4_audio"
            except Exception as e:
                logger.warning(f"設定ファイルの読み込み中に予期せぬエラーが発生しました: {str(e)}。デフォルトの書き起こし方式を使用します。")
                return "gpt4_audio"
            
            method = config.get("transcription", {}).get("method", "gpt4_audio")
            if method not in ["whisper_gpt4", "gpt4_audio"]:
                logger.warning(f"無効な書き起こし方式が指定されています: {method}")
                logger.info("デフォルトの書き起こし方式を使用します。")
                return "gpt4_audio"
            
            return method
            
        except Exception as e:
            logger.error(f"設定ファイルの処理中に予期せぬエラーが発生しました: {str(e)}")
            return "gpt4_audio"

    def process_audio(self, audio_file: pathlib.Path, additional_prompt: str = "") -> Dict[str, Any]:
        """音声ファイルの書き起こし処理を実行"""
        try:
            logger.info(f"書き起こしを開始: {audio_file}")
            logger.info(f"音声ファイルサイズ: {audio_file.stat().st_size:,} bytes")
            logger.info(f"使用する書き起こし方式: {self.transcription_method}")
            
            # タイムスタンプの生成
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            logger.info(f"タイムスタンプ: {timestamp}")

            if self.transcription_method == "whisper_gpt4":
                return self._process_with_whisper_gpt4(audio_file, additional_prompt, timestamp)
            else:  # gpt4_audio
                return self._process_with_gpt4_audio(audio_file, timestamp)
            
        except Exception as e:
            logger.error(f"書き起こし処理中にエラーが発生しました: {str(e)}")
            raise TranscriptionError(f"書き起こしに失敗しました: {str(e)}")

    def _process_with_whisper_gpt4(self, audio_file: pathlib.Path, additional_prompt: str, timestamp: str) -> Dict[str, Any]:
        """Whisper + GPT-4方式での書き起こし処理"""
        # 音声からテキストを生成
        logger.info("Whisperで音声認識を開始")
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
        
        logger.info("Whisper + GPT-4方式での書き起こし処理が完了しました")
        return {
            "raw_text": transcription,
            "formatted_text": formatted_text,
            "raw_file": raw_output_path,
            "formatted_file": formatted_output_path,
            "timestamp": timestamp
        }

    def _process_with_gpt4_audio(self, audio_file: pathlib.Path, timestamp: str) -> Dict[str, Any]:
        """GPT-4 Audio方式での書き起こし処理"""
        logger.info("GPT-4 Audioで音声認識・整形を開始")
        
        formatted_text = generate_audio_chat_response(str(audio_file), self.system_prompt)
        
        if not formatted_text:
            logger.error("音声認識・整形の結果が空です")
            raise TranscriptionError("書き起こしの生成に失敗しました")
        
        logger.info(f"音声認識・整形完了（テキスト長: {len(formatted_text)}文字）")
        
        # 整形済みテキストを保存
        formatted_output_path = self.output_dir / f"transcription_summary_{timestamp}.txt"
        logger.info(f"整形済みテキストを保存: {formatted_output_path}")
        try:
            with open(formatted_output_path, "w", encoding="utf-8") as f:
                f.write(formatted_text)
        except Exception as e:
            logger.error(f"整形済みテキストの保存中にエラー: {str(e)}")
            raise TranscriptionError(f"整形済みテキストの保存に失敗しました: {str(e)}")
        
        logger.info("GPT-4 Audio方式での書き起こし処理が完了しました")
        return {
            "raw_text": "",  # GPT-4 Audio方式では生テキストは生成されない
            "formatted_text": formatted_text,
            "raw_file": None,  # GPT-4 Audio方式では生テキストファイルは生成されない
            "formatted_file": formatted_output_path,
            "timestamp": timestamp
        }

    def get_output_path(self, timestamp: str = None) -> pathlib.Path:
        """出力ファイルパスの生成"""
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return self.output_dir / f"transcription_summary_{timestamp}.txt" 