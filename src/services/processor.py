import logging
from pathlib import Path
from typing import Dict, Any
from .audio import AudioProcessor, AudioProcessingError
from .transcription import TranscriptionService
from .csv_converter import CSVConverterService
from .minutes import MinutesService
from .format_converter import convert_file, cleanup_file, FormatConversionError
from .meeting_title_service import MeetingTitleService

logger = logging.getLogger(__name__)

def process_audio_file(input_file: Path, modes: dict) -> dict:
    """音声ファイルの処理を実行"""
    results = {}
    
    logger.info(f"処理開始 - 入力ファイル: {input_file}")
    logger.info(f"モード設定: {modes}")
    
    # 追加: 変換フラグおよび変換後ファイル保持用変数の初期化
    conversion_performed = False
    converted_file = None

    try:
        # 追加: ファイル形式の判定・変換処理
        original_path = str(input_file)
        try:
            converted = convert_file(original_path)
            if converted != original_path:
                conversion_performed = True
                converted_file = Path(converted)
                logger.info(f"変換が実施されました。変換後のファイルを使用します: {converted_file}")
                input_file = converted_file
            else:
                logger.info("ファイル形式は既に対応済みのため変換は不要です。")
        except FormatConversionError as e:
            logger.error(f"ファイル形式の変換に失敗しました: {str(e)}")
            raise AudioProcessingError(f"ファイル形式の変換に失敗しました: {str(e)}")

        # 音声処理サービスの初期化
        audio_processor = AudioProcessor()
        
        # 音声の抽出と必要に応じた圧縮
        logger.info(f"音声ファイルの処理を開始: {input_file}")
        audio_file, was_compressed = audio_processor.extract_audio(input_file)
        logger.info(f"音声処理完了 - 圧縮状態: {was_compressed}")
        
        try:
            # 書き起こし処理（必須）
            if modes["transcribe"]:
                logger.info("書き起こし処理を開始")
                transcription_service = TranscriptionService()
                transcription_result = transcription_service.process_audio(audio_file)
                results["transcription"] = transcription_result
                
                # 会議タイトル生成処理を追加
                try:
                    logger.info("会議タイトル生成処理を開始")
                    # タイトル出力ディレクトリの確認と作成
                    title_output_dir = Path("output/title")
                    if not title_output_dir.exists():
                        title_output_dir.mkdir(parents=True, exist_ok=True)
                        logger.info(f"タイトル出力ディレクトリを作成しました: {title_output_dir}")

                    title_service = MeetingTitleService()
                    transcript_file_path = transcription_result.get("formatted_file")
                    if transcript_file_path:
                        title_file_path = title_service.process_transcript_and_generate_title(str(transcript_file_path))
                        results["meeting_title"] = {"file_path": title_file_path}
                        logger.info(f"会議タイトル生成完了: {title_file_path}")
                    else:
                        logger.warning("書き起こしファイルのパスが見つかりません")
                except Exception as e:
                    logger.error(f"会議タイトル生成中にエラーが発生: {str(e)}")
                    results["meeting_title"] = {"error": str(e)}
                
                # CSV変換
                logger.info("CSV変換を開始")
                csv_converter = CSVConverterService()
                csv_file = csv_converter.convert_to_csv(transcription_result["formatted_file"])
                results["csv"] = csv_file
            
            # 議事録生成
            if modes["minutes"]:
                logger.info("議事録生成を開始")
                minutes_service = MinutesService()
                minutes_result = minutes_service.generate_minutes(transcription_result["formatted_file"])
                # 戻り値のキーを適切に取り扱う
                results["minutes"] = minutes_result.get("file_path") or minutes_result.get("minutes_file")
                if not results["minutes"]:
                    logger.error("議事録ファイルのパスが取得できませんでした")
                    raise ValueError("議事録ファイルのパスが取得できませんでした")
            
            # 反省点抽出
            if modes["reflection"]:
                logger.info("反省点抽出を開始")
                minutes_service = MinutesService()
                
                # 議事録ファイルの内容を読み込む
                with open(results["minutes"], "r", encoding="utf-8") as f:
                    minutes_text = f.read()
                
                reflection_text = minutes_service.generate_reflection(minutes_text)
                
                # 反省点をファイルに保存（タイムスタンプベースのファイル名に変更）
                reflection_file = Path("output/minutes") / f"{transcription_result['timestamp']}_reflection.md"
                reflection_file.write_text(reflection_text, encoding="utf-8")
                results["reflection"] = reflection_file
                logger.info(f"反省点を保存しました: {reflection_file}")
            
            logger.info("全ての処理が完了しました")
            return results
            
        finally:
            # 既存: 一時ファイルのクリーンアップ
            if was_compressed and audio_file.exists():
                audio_file.unlink()
            # 追加: 変換処理で生成した一時ファイルの削除
            if conversion_performed and converted_file is not None and converted_file.exists():
                try:
                    cleanup_file(str(converted_file))
                except FormatConversionError as e:
                    logger.warning(f"一時ファイルの削除中にエラーが発生しました: {str(e)}")
                
    except Exception as e:
        logger.error(f"処理中にエラーが発生しました: {str(e)}")
        raise 