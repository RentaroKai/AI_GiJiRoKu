import os
import pathlib
import logging
import datetime
import json
from typing import Dict, Any, Literal
from ..utils.Common_OpenAIAPI import generate_transcribe_from_audio, generate_structured_chat_response, generate_audio_chat_response, APIError, MEETING_TRANSCRIPT_SCHEMA
from ..utils.gemini_api import GeminiAPI
import sys
from ..modules.audio_splitter import AudioSplitter
from pathlib import Path
import re

logger = logging.getLogger(__name__)

def add_speaker_identifier(text, identifier):
    """
    文字起こしテキスト内の話者名に識別子を付加する

    Args:
        text (str): 元の文字起こしテキスト
        identifier (str): 付加する識別子 (例: "seg1")

    Returns:
        str: 話者名に識別子が付加されたテキスト
    """
    # テキストがJSON形式かを確認
    try:
        # JSONとして解析を試みる
        if text.strip().startswith('{') or text.strip().startswith('['):
            data = json.loads(text)

            # JSONオブジェクトの場合
            if isinstance(data, dict):
                if "speaker" in data:
                    data["speaker"] = f"{data['speaker']}_{identifier}"
                # 会話リストを含む場合
                if "conversations" in data and isinstance(data["conversations"], list):
                    for conversation in data["conversations"]:
                        if isinstance(conversation, dict) and "speaker" in conversation:
                            conversation["speaker"] = f"{conversation['speaker']}_{identifier}"

            # JSON配列の場合
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "speaker" in item:
                        item["speaker"] = f"{item['speaker']}_{identifier}"

            return json.dumps(data, ensure_ascii=False)
    except (json.JSONDecodeError, AttributeError):
        # JSONとして解析できない場合は通常のテキストとして処理
        pass

    # 通常のテキストの場合、正規表現で話者名を識別して置換
    # 一般的な話者パターン: "話者名:" や "話者名 :"
    text = re.sub(r'(話者\d+)\s*:', r'\1_' + identifier + ':', text)
    text = re.sub(r'(スピーカー\d+)\s*:', r'\1_' + identifier + ':', text)
    text = re.sub(r'(Speaker\s*\d+)\s*:', r'\1_' + identifier + ':', text)

    # 不正なJSONの場合でも話者名を識別して置換（JSONっぽい文字列の場合）
    if '"speaker"' in text:
        text = re.sub(r'"speaker"\s*:\s*"([^"]*)"', r'"speaker": "\1_' + identifier + '"', text)

    return text

class TranscriptionError(Exception):
    """書き起こし処理関連のエラーを扱うカスタム例外クラス"""
    pass

class TranscriptionService:
    def __init__(self, output_dir: str = "output/transcriptions", config_path: str = "config/settings.json"):
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"出力ディレクトリを作成/確認: {self.output_dir}")

        # 実行環境の確認
        is_frozen = getattr(sys, 'frozen', False)
        logger.info(f"TranscriptionService初期化: 実行モード={'PyInstaller' if is_frozen else '通常'}")

        # PyInstallerモードでの設定ファイルパスの解決
        if is_frozen:
            exe_dir = pathlib.Path(sys.executable).parent
            alt_config_path = exe_dir / config_path
            if alt_config_path.exists():
                logger.info(f"PyInstaller実行モード: 代替設定ファイルを使用 - {alt_config_path}")
                config_path = str(alt_config_path)
            else:
                logger.warning(f"PyInstaller実行モード: 代替設定ファイルが見つかりません - {alt_config_path}")

        logger.info(f"使用する設定ファイルパス: {config_path}")

        # 設定の読み込み
        self.config = self._load_config(config_path)
        self.transcription_method = self.config.get("transcription", {}).get("method", "gpt4_audio")
        logger.info(f"書き起こし方式: {self.transcription_method}")

        # 再試行フラグの初期化
        self.has_reached_max_retries = False

        # Gemini APIの初期化（Gemini方式が選択されている場合）
        if self.transcription_method == "gemini":
            self.gemini_api = GeminiAPI()
            logger.info("Gemini APIを初期化しました")

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

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """設定ファイルから設定を読み込む"""
        try:
            logger.info(f"設定ファイルを読み込み開始: {config_path}")
            config_file = pathlib.Path(config_path)

            if not config_file.exists():
                logger.info("設定ファイルが見つかりません。デフォルトの設定を使用します。")
                default_config = {"transcription": {"method": "gpt4_audio"}}
                logger.info(f"デフォルト設定内容: {default_config}")
                return default_config

            try:
                logger.info(f"設定ファイルを読み込み中: {config_file} (サイズ: {config_file.stat().st_size} bytes)")
                with open(config_file, "r", encoding="utf-8") as f:
                    config_text = f.read().strip()
                    # 空ファイルチェック
                    if not config_text:
                        logger.warning("設定ファイルが空です。デフォルトの設定を使用します。")
                        default_config = {"transcription": {"method": "gpt4_audio"}}
                        logger.info(f"空ファイル時のデフォルト設定内容: {default_config}")
                        return default_config

                    # 文字列を整形して余分な文字を削除
                    config_text = config_text.replace('\n', '').replace('\r', '').strip()
                    # 最後のカンマを削除（一般的なJSON解析エラーの原因）
                    if config_text.endswith(',}'):
                        config_text = config_text[:-2] + '}'

                    logger.info(f"設定ファイル内容（処理後）: {config_text[:100]}...")
                    config = json.loads(config_text)
            except json.JSONDecodeError as e:
                logger.warning(f"設定ファイルのJSONパースに失敗しました: {str(e)}。デフォルトの設定を使用します。")
                default_config = {"transcription": {"method": "gpt4_audio"}}
                logger.info(f"JSONエラー時のデフォルト設定内容: {default_config}")
                return default_config
            except Exception as e:
                logger.warning(f"設定ファイルの読み込み中に予期せぬエラーが発生しました: {str(e)}。デフォルトの設定を使用します。")
                default_config = {"transcription": {"method": "gpt4_audio"}}
                logger.info(f"その他エラー時のデフォルト設定内容: {default_config}")
                return default_config

            method = config.get("transcription", {}).get("method", "gpt4_audio")
            logger.info(f"読み込まれた書き起こし方式: {method}")

            if method not in ["whisper_gpt4", "gpt4_audio", "gemini"]:
                logger.warning(f"無効な書き起こし方式が指定されています: {method}")
                logger.info("デフォルトの書き起こし方式を使用します。")
                config["transcription"]["method"] = "gpt4_audio"

            return config

        except Exception as e:
            logger.error(f"設定ファイルの処理中に予期せぬエラーが発生しました: {str(e)}")
            default_config = {"transcription": {"method": "gpt4_audio"}}
            logger.info(f"最終エラー時のデフォルト設定内容: {default_config}")
            return default_config

    def process_audio(self, audio_file: pathlib.Path, additional_prompt: str = "") -> Dict[str, Any]:
        """音声ファイルの書き起こし処理を実行"""
        try:
            logger.info(f"書き起こしを開始: {audio_file}")
            logger.info(f"音声ファイルサイズ: {audio_file.stat().st_size:,} bytes")
            logger.info(f"使用する書き起こし方式: {self.transcription_method}")

            # 再試行フラグをリセット
            self.has_reached_max_retries = False

            # タイムスタンプの生成
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            logger.info(f"タイムスタンプ: {timestamp}")

            # 書き起こし処理の実行
            if self.transcription_method == "whisper_gpt4":
                result = self._process_with_whisper_gpt4(audio_file, additional_prompt, timestamp)
            elif self.transcription_method == "gemini":
                result = self._process_with_gemini(audio_file, timestamp)
            else:  # gpt4_audio
                result = self._process_with_gpt4_audio(audio_file, timestamp)

            # 処理完了後、最大再試行回数に達したかどうかをチェックして通知
            if self.has_reached_max_retries:
                result["warning"] = "一部のセグメントで最大再試行回数に達しました。文字起こし結果にエラーが含まれている可能性があります。"
                logger.warning("警告: 一部のセグメントで最大再試行回数に達しました。文字起こし結果にエラーが含まれている可能性があります。")

            return result

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

        # 再試行メカニズムを追加
        max_retries = 2
        formatted_text = None

        for attempt in range(max_retries + 1):
            try:
                formatted_text = generate_structured_chat_response(
                    system_prompt=self.system_prompt,
                    user_message_content=full_prompt,
                    json_schema=MEETING_TRANSCRIPT_SCHEMA
                )

                # 問題のあるパターンをチェック
                if formatted_text and self.is_problematic_transcription(formatted_text):
                    logger.warning(f"整形結果で問題のあるパターンが検出されました")
                    if attempt < max_retries:
                        logger.warning(f"整形結果に問題のあるパターンが検出されました。再試行します ({attempt+1}/{max_retries})")
                        continue
                    else:
                        logger.error(f"整形処理が最大再試行回数に達しました。最後の結果を使用します。")
                else:
                    logger.info("整形結果は正常なテキストと判断されました")
                break
            except Exception as e:
                logger.error(f"テキスト整形中にエラー: {str(e)}")
                if attempt < max_retries:
                    logger.warning(f"再試行します ({attempt+1}/{max_retries})")
                else:
                    logger.error(f"最大再試行回数に達しました。")
                    self.has_reached_max_retries = True  # エラー表示のためのフラグ
                    raise TranscriptionError(f"テキストの整形に失敗しました: {str(e)}")

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

        try:
            # 設定から分割長を取得（デフォルトは100秒）
            segment_length = self.config.get('transcription', {}).get('segment_length_seconds', 100)
            logger.info(f"設定された分割長: {segment_length}秒")

            # AudioSplitterの初期化（設定された分割長を使用）
            splitter = AudioSplitter(segment_length_seconds=segment_length)

            # セグメント保存用の一時ディレクトリを作成
            segments_dir = self.output_dir / "segments" / timestamp
            segments_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"セグメント一時ディレクトリを作成: {segments_dir}")

            # 音声ファイルを分割
            logger.info("音声ファイルの分割を開始")
            split_files = splitter.split_audio(str(audio_file), str(segments_dir))
            logger.info(f"音声を {len(split_files)} 個のセグメントに分割しました")

            # 各セグメントの文字起こし結果を保存
            all_transcriptions = []
            for i, segment_file in enumerate(split_files, 1):
                logger.info(f"セグメント {i}/{len(split_files)} の文字起こしを実行中...")

                # セグメントの文字起こし処理部分を変更
                max_retries = 2  # 最大再試行回数
                segment_text = None

                for attempt in range(max_retries + 1):
                    try:
                        segment_text_raw = generate_audio_chat_response(str(segment_file), self.system_prompt)
                        # 文字起こし結果の余分な空白を除去
                        segment_text = re.sub(r'\s+', ' ', segment_text_raw).strip() if segment_text_raw else ""

                        logger.info(f"セグメント {i} の文字起こし結果: 文字数={len(segment_text)}")
                        logger.debug(f"セグメント {i} の文字起こし結果（先頭100文字）: {segment_text[:100]}...")

                        # 問題のあるパターンをチェック
                        logger.info(f"セグメント {i} の繰り返しパターンチェックを実行")
                        if segment_text and self.is_problematic_transcription(segment_text):
                            logger.warning(f"セグメント {i} で問題のあるパターンが検出されました")
                            if attempt < max_retries:
                                logger.warning(f"セグメント {i} に問題のあるパターンが検出されました。再試行します ({attempt+1}/{max_retries})")
                                continue
                            else:
                                logger.error(f"セグメント {i} の処理が最大再試行回数に達しました。最後の結果を使用します。")
                        else:
                            logger.info(f"セグメント {i} は正常なテキストと判断されました")
                        # 問題なければループを抜ける
                        break
                    except Exception as e:
                        logger.error(f"セグメント {i} の文字起こし中にエラー: {str(e)}")
                        if attempt < max_retries:
                            logger.warning(f"再試行します ({attempt+1}/{max_retries})")
                        else:
                            logger.error(f"最大再試行回数に達しました。このセグメントをスキップします。")
                            self.has_reached_max_retries = True  # エラー表示のためのフラグ
                            segment_text = ""

                if not segment_text:
                    logger.warning(f"セグメント {i} の文字起こし結果が空です")
                    continue

                # 話者名に識別子を付加 (セグメント番号を使用)
                segment_identifier = f"seg{i}"
                segment_text = add_speaker_identifier(segment_text, segment_identifier)
                logger.info(f"セグメント {i} の話者名に識別子 '{segment_identifier}' を付加しました")

                # セグメント情報を追加
                segment_result = {
                    "segment": i,
                    "segment_file": Path(segment_file).name,
                    "text": segment_text
                }
                all_transcriptions.append(segment_result)
                logger.info(f"セグメント {i} の文字起こしが完了")

            # 中間結果をJSONとして保存
            complete_result = {
                "metadata": {
                    "total_segments": len(split_files),
                    "original_file": str(audio_file)
                },
                "segments": all_transcriptions
            }

            complete_json_path = self.output_dir / f"complete_transcription_{timestamp}.json"
            with open(complete_json_path, "w", encoding="utf-8") as f:
                json.dump(complete_result, f, ensure_ascii=False, indent=2)
            logger.info(f"中間結果をJSONとして保存: {complete_json_path}")

            # 全セグメントの結果を結合
            combined_text = "".join(seg["text"] for seg in all_transcriptions)
            formatted_text = re.sub(r'\s+', ' ', combined_text).strip()
            formatted_text = re.sub(r'(?<=[\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])\s+(?=[\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])', '', formatted_text)

            # 最終結果を保存
            formatted_output_path = self.output_dir / f"transcription_summary_{timestamp}.txt"
            formatted_output_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                with open(formatted_output_path, "w", encoding="utf-8") as f:
                    f.write(formatted_text)
            except Exception as e:
                logger.error(f"整形済みテキストの保存中にエラー: {str(e)}")
                raise TranscriptionError(f"整形済みテキストの保存に失敗しました: {str(e)}")

            # 一時ファイルのクリーンアップ
            try:
                import shutil
                shutil.rmtree(segments_dir)
                logger.info("一時ファイルのクリーンアップが完了しました")
            except Exception as e:
                logger.warning(f"一時ファイルのクリーンアップ中にエラー: {str(e)}")

            logger.info("GPT-4 Audio方式での書き起こし処理が完了しました")
            return {
                "raw_text": "",  # GPT-4 Audio方式では生テキストは生成されない
                "formatted_text": formatted_text,
                "raw_file": None,
                "formatted_file": formatted_output_path,
                "timestamp": timestamp
            }

        except Exception as e:
            logger.error(f"GPT-4 Audio方式での処理中にエラー: {str(e)}")
            raise TranscriptionError(f"GPT-4 Audio方式での処理に失敗しました: {str(e)}")

    def _process_with_gemini(self, audio_file: pathlib.Path, timestamp: str) -> Dict[str, Any]:
        """Gemini方式での書き起こし処理"""
        logger.info("Geminiで音声認識・整形を開始")

        try:
            # 設定から分割長を取得（デフォルトは100秒）
            segment_length = self.config.get('transcription', {}).get('segment_length_seconds', 100)
            logger.info(f"設定された分割長: {segment_length}秒")

            # AudioSplitterの初期化（設定された分割長を使用）
            splitter = AudioSplitter(segment_length_seconds=segment_length)

            # セグメント保存用の一時ディレクトリを作成
            segments_dir = self.output_dir / "segments" / timestamp
            segments_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"セグメント一時ディレクトリを作成: {segments_dir}")

            # 音声ファイルを分割
            logger.info("音声ファイルの分割を開始")
            split_files = splitter.split_audio(str(audio_file), str(segments_dir))
            logger.info(f"音声を {len(split_files)} 個のセグメントに分割しました")

            # 各セグメントの文字起こし結果を保存
            all_transcriptions = []
            for i, segment_file in enumerate(split_files, 1):
                logger.info(f"セグメント {i}/{len(split_files)} の文字起こしを実行中...")

                # セグメントの文字起こし処理部分を変更
                max_retries = 2  # 最大再試行回数
                segment_text = None

                for attempt in range(max_retries + 1):
                    try:
                        segment_text_raw = self.gemini_api.transcribe_audio(str(segment_file))
                        # 文字起こし結果の余分な空白を除去
                        segment_text = re.sub(r'\s+', ' ', segment_text_raw).strip() if segment_text_raw else ""

                        logger.info(f"セグメント {i} の文字起こし結果: 文字数={len(segment_text)}")
                        logger.debug(f"セグメント {i} の文字起こし結果（先頭100文字）: {segment_text[:100]}...")

                        # 問題のあるパターンをチェック
                        logger.info(f"セグメント {i} の繰り返しパターンチェックを実行")
                        if segment_text and self.is_problematic_transcription(segment_text):
                            logger.warning(f"セグメント {i} で問題のあるパターンが検出されました")
                            if attempt < max_retries:
                                logger.warning(f"セグメント {i} に問題のあるパターンが検出されました。再試行します ({attempt+1}/{max_retries})")
                                continue
                            else:
                                logger.error(f"セグメント {i} の処理が最大再試行回数に達しました。最後の結果を使用します。")
                                self.has_reached_max_retries = True  # エラー表示のためのフラグ
                        else:
                            logger.info(f"セグメント {i} は正常なテキストと判断されました")
                        # 問題なければループを抜ける
                        break
                    except Exception as e:
                        logger.error(f"セグメント {i} の文字起こし中にエラー: {str(e)}")
                        if attempt < max_retries:
                            logger.warning(f"再試行します ({attempt+1}/{max_retries})")
                        else:
                            logger.error(f"最大再試行回数に達しました。このセグメントをスキップします。")
                            self.has_reached_max_retries = True  # エラー表示のためのフラグ
                            segment_text = ""

                if not segment_text:
                    logger.warning(f"セグメント {i} の文字起こし結果が空です")
                    continue

                # 話者名に識別子を付加 (セグメント番号を使用)
                segment_identifier = f"seg{i}"
                segment_text = add_speaker_identifier(segment_text, segment_identifier)
                logger.info(f"セグメント {i} の話者名に識別子 '{segment_identifier}' を付加しました")

                # セグメント情報を追加
                segment_result = {
                    "segment": i,
                    "segment_file": Path(segment_file).name,
                    "text": segment_text
                }
                all_transcriptions.append(segment_result)
                logger.info(f"セグメント {i} の文字起こしが完了")

            # 中間結果をJSONとして保存
            complete_result = {
                "metadata": {
                    "total_segments": len(split_files),
                    "original_file": str(audio_file)
                },
                "segments": all_transcriptions
            }

            complete_json_path = self.output_dir / f"complete_transcription_{timestamp}.json"
            with open(complete_json_path, "w", encoding="utf-8") as f:
                json.dump(complete_result, f, ensure_ascii=False, indent=2)
            logger.info(f"中間結果をJSONとして保存: {complete_json_path}")

            # 全セグメントの結果を結合
            combined_text = "".join(seg["text"] for seg in all_transcriptions)
            formatted_text = re.sub(r'\s+', ' ', combined_text).strip()
            formatted_text = re.sub(r'(?<=[\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])\s+(?=[\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])', '', formatted_text)

            # 最終結果を保存
            formatted_output_path = self.output_dir / f"transcription_summary_{timestamp}.txt"
            formatted_output_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                with open(formatted_output_path, "w", encoding="utf-8") as f:
                    f.write(formatted_text)
            except Exception as e:
                logger.error(f"整形済みテキストの保存中にエラー: {str(e)}")
                raise TranscriptionError(f"整形済みテキストの保存に失敗しました: {str(e)}")

            # 一時ファイルのクリーンアップ
            try:
                import shutil
                shutil.rmtree(segments_dir)
                logger.info("一時ファイルのクリーンアップが完了しました")
            except Exception as e:
                logger.warning(f"一時ファイルのクリーンアップ中にエラー: {str(e)}")

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

    def get_output_path(self, timestamp: str = None) -> pathlib.Path:
        """出力ファイルパスの生成"""
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return self.output_dir / f"transcription_summary_{timestamp}.txt"

    def is_problematic_transcription(self, text):
        """
        指定されたテキストが問題のあるパターンを含むかどうかを判断します

        Args:
            text (str): チェックする文字起こしテキスト

        Returns:
            bool: 問題がある場合はTrue、それ以外はFalse
        """
        logger.info(f"繰り返しパターンのチェックを実行: テキスト長={len(text)}")
        if not text:
            return False

        # "Take minutes of the meeting"を含むかチェック
        if "Take minutes of the meeting" in text:
            logger.warning("問題パターン検出: 'Take minutes of the meeting'")
            return True

        # 方法1: 単語の繰り返しをチェック（日本語・英語両方対応）
        logger.debug(f"単語の繰り返しをチェック: {text[:100]}...")
        words = text.split()

        # 繰り返しパターンのチェック（シンプルな方法）
        for i in range(len(words)):
            word = words[i]
            # 話者名（「話者1:」など）は繰り返しチェックから除外
            if re.match(r'(話者\d+[_\w]*|スピーカー\d+[_\w]*|Speaker\s*\d+[_\w]*)\s*:', word):
                continue

            count = 1
            # 同じ単語が連続しているかをカウント
            for j in range(i+1, len(words)):
                if words[j] == word:
                    count += 1
                else:
                    break

            if count >= 100:  # 閾値を20から100に引き上げ
                logger.warning(f"問題パターン検出: 単語 '{word}' が {count} 回繰り返されています")
                return True

        # 方法2: フレーズの繰り返しをチェック（句読点を含む）
        logger.debug("フレーズの繰り返しをチェック")
        # 正規表現で短いフレーズの繰り返しを検出
        # 例: 「うん。」「はい。」などが繰り返される場合
        short_phrases = re.findall(r'(.{1,5}[。、．，!！?？\s]+)', text)
        phrase_counts = {}

        for phrase in short_phrases:
            phrase = phrase.strip()

            # 単一の記号や括弧のみのフレーズは除外
            if not phrase or re.match(r'^[{}\[\]()<>「」『』【】\'\"]+$', phrase):
                continue

            # 話者名を含むフレーズは除外
            if re.search(r'(話者\d+[_\w]*|スピーカー\d+[_\w]*|Speaker\s*\d+[_\w]*)\s*:', phrase):
                continue

            if phrase:
                if phrase in phrase_counts:
                    phrase_counts[phrase] += 1
                else:
                    phrase_counts[phrase] = 1

        # 同じフレーズが大量に繰り返されているかチェック
        for phrase, count in phrase_counts.items():
            if count >= 100:  # 閾値を15から100に引き上げ
                logger.warning(f"問題パターン検出: フレーズ '{phrase}' が {count} 回繰り返されています")
                return True

        # 方法3: 文字列のN-gramパターンをチェック（日本語のような分かち書きされない言語向け）
        logger.debug("N-gramパターンのチェック")
        n_values = [2, 3, 4]  # バイグラム、トライグラム、4-gramをチェック

        for n in n_values:
            # N-gramを生成
            ngrams = [text[i:i+n] for i in range(len(text) - n + 1)]

            # 特定のパターンを除外
            filtered_ngrams = []
            for ng in ngrams:
                # 単一の記号や括弧のみは除外
                if re.match(r'^[{}\[\]()<>「」『』【】\'\"]+$', ng):
                    continue
                filtered_ngrams.append(ng)

            # 連続する同じN-gramをカウント
            for i in range(len(filtered_ngrams)):
                if i >= len(filtered_ngrams) - 10:  # 残りの長さが短すぎる場合はスキップ
                    break

                current_ngram = filtered_ngrams[i]
                # 単一の記号や括弧のみは除外
                if re.match(r'^[{}\[\]()<>「」『』【】\'\"]+$', current_ngram):
                    continue

                count = 1

                # 同じN-gramが連続するかをチェック
                for j in range(i+1, min(i+150, len(filtered_ngrams))):  # 検索範囲を拡大
                    if filtered_ngrams[j] == current_ngram:
                        count += 1
                        if count >= 100:  # 閾値を10から100に引き上げ
                            logger.warning(f"問題パターン検出: N-gram '{current_ngram}' が {count} 回繰り返されています")
                            return True
                    else:
                        # 連続していない場合はカウントをリセット
                        if count >= 10:  # デバッグログの閾値も調整
                            logger.debug(f"N-gram '{current_ngram}' が {count} 回連続しました（閾値未満）")
                        count = 1

        logger.info("繰り返しパターンは検出されませんでした")
        return False