import os
import pathlib
import logging
#import datetime
import sys
from typing import Dict, Any
from ..utils.Common_OpenAIAPI import generate_chat_response, APIError
from pathlib import Path

logger = logging.getLogger(__name__)

class MinutesError(Exception):
    """議事録生成関連のエラーを扱うカスタム例外クラス"""
    pass

class MinutesService:
    def __init__(self, output_dir: str = "output/minutes"):
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"出力ディレクトリを作成/確認: {self.output_dir}")
        
        # プロンプトの読み込み
        if getattr(sys, 'frozen', False):
            # PyInstallerで実行している場合
            base_path = pathlib.Path(sys._MEIPASS)
            prompt_path = base_path / "src/prompts/minutes.txt"
            logger.info(f"PyInstaller実行モード - MEIPASS: {base_path}")
            logger.info(f"PyInstaller実行モード - プロンプトパス: {prompt_path}")
            # MEIPASSディレクトリの内容を確認
            logger.info(f"MEIPASSディレクトリ内容:")
            for item in base_path.glob("**/*"):
                logger.info(f"  {item}")
        else:
            # 通常の実行の場合
            prompt_path = pathlib.Path("src/prompts/minutes.txt")
            logger.info(f"通常実行モード - プロンプトパス: {prompt_path}")
            logger.info(f"現在のディレクトリ: {os.getcwd()}")
        
        if not prompt_path.exists():
            logger.error(f"議事録プロンプトファイルが見つかりません: {prompt_path}")
            logger.error(f"現在のディレクトリ: {os.getcwd()}")
            logger.error(f"ディレクトリ内容:")
            if prompt_path.parent.exists():
                for item in prompt_path.parent.glob("**/*"):
                    logger.error(f"  {item}")
            else:
                logger.error(f"親ディレクトリが存在しません: {prompt_path.parent}")
            raise MinutesError(f"議事録プロンプトファイルが見つかりません: {prompt_path}")
        
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
                raise MinutesError(f"プロンプトファイルの読み込みに失敗しました: {str(e)} -> {str(e2)}")
        except Exception as e:
            logger.error(f"プロンプトファイルの読み込み中にエラー: {str(e)}")
            raise MinutesError(f"プロンプトファイルの読み込みに失敗しました: {str(e)}")

    def generate_minutes(self, transcription_file: pathlib.Path) -> Dict[str, Any]:
        """書き起こしデータから議事録を生成"""
        try:
            logger.info(f"議事録生成を開始: {transcription_file}")
            logger.info(f"入力ファイルサイズ: {transcription_file.stat().st_size:,} bytes")
            
            # 書き起こしデータの読み込み
            try:
                with open(transcription_file, "r", encoding="utf-8") as f:
                    transcription_text = f.read()
                logger.info(f"書き起こしデータを読み込みました（長さ: {len(transcription_text)}文字）")
            except UnicodeDecodeError as e:
                logger.error(f"書き起こしファイルのエンコーディングエラー: {str(e)}")
                # UTF-8で失敗した場合、CP932で試行
                try:
                    with open(transcription_file, "r", encoding="cp932") as f:
                        transcription_text = f.read()
                    logger.info(f"CP932エンコーディングで書き起こしデータを読み込みました（長さ: {len(transcription_text)}文字）")
                except Exception as e2:
                    logger.error(f"CP932でも読み込みに失敗: {str(e2)}")
                    raise MinutesError(f"書き起こしファイルの読み込みに失敗しました: {str(e)} -> {str(e2)}")
            
            if not transcription_text:
                logger.error("書き起こしデータが空です")
                raise MinutesError("書き起こしデータが空です")
            
            # GPT-4oで議事録生成
            logger.info("GPT-4oで議事録生成を開始")
            minutes_text = generate_chat_response(
                self.system_prompt,
                transcription_text
            )
            
            if not minutes_text:
                logger.error("議事録の生成結果が空です")
                raise MinutesError("議事録の生成に失敗しました")
            
            logger.info(f"議事録生成完了（長さ: {len(minutes_text)}文字）")
            
            # 出力ファイルパスの生成
            output_file = self.output_dir / f"{transcription_file.stem}_minutes.md"
            logger.info(f"議事録を保存: {output_file}")
            
            # 議事録の保存
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(minutes_text)
            except Exception as e:
                logger.error(f"議事録の保存中にエラー: {str(e)}")
                raise MinutesError(f"議事録の保存に失敗しました: {str(e)}")
            
            logger.info(f"議事録生成が完了しました: {output_file}")
            return {
                "minutes_text": minutes_text,
                "minutes_file": output_file
            }
            
        except APIError as e:
            logger.error(f"API処理中にエラーが発生しました: {str(e)}")
            raise MinutesError(f"APIエラー: {str(e)}")
        except Exception as e:
            logger.error(f"議事録生成中にエラーが発生しました: {str(e)}")
            logger.error(f"エラータイプ: {type(e).__name__}")
            raise MinutesError(f"議事録生成に失敗しました: {str(e)}")

    def get_output_path(self, transcription_file: pathlib.Path) -> pathlib.Path:
        """出力ファイルパスの生成"""
        return self.output_dir / f"{transcription_file.stem}_minutes.md"

    def generate_reflection(self, text: str) -> str:
        """
        会議の反省点と改善点を生成する
        
        Args:
            text (str): 議事録のテキスト
        
        Returns:
            str: 反省点と改善点を含む分析結果
        """
        try:
            logging.info("会議の反省点分析を開始します")
            
            if not text:
                logger.error("議事録データが空です")
                raise MinutesError("議事録データが空です")
            
            # プロンプトの読み込み
            if getattr(sys, 'frozen', False):
                # PyInstallerで実行している場合
                base_path = pathlib.Path(sys._MEIPASS)
                prompt_path = base_path / "src/prompts/reflection.txt"
            else:
                # 通常の実行の場合
                prompt_path = pathlib.Path("src/prompts/reflection.txt")
            
            if not prompt_path.exists():
                logger.error(f"反省点プロンプトファイルが見つかりません: {prompt_path}")
                raise MinutesError(f"反省点プロンプトファイルが見つかりません: {prompt_path}")
            
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    prompt_template = f.read().strip()
            except Exception as e:
                logger.error(f"反省点プロンプトファイルの読み込みに失敗: {str(e)}")
                raise MinutesError(f"反省点プロンプトファイルの読み込みに失敗: {str(e)}")
            
            # GPT-4による分析
            reflection_result = generate_chat_response(
                prompt_template,
                text
            )
            
            if not reflection_result:
                error_msg = "反省点の生成結果が空です"
                logging.error(error_msg)
                raise MinutesError(error_msg)
            
            logging.info("反省点分析が完了しました")
            return reflection_result
            
        except Exception as e:
            error_msg = f"反省点分析中にエラーが発生しました: {str(e)}"
            logging.error(error_msg)
            raise MinutesError(error_msg) 