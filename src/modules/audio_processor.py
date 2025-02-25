import logging
from pathlib import Path
import json
from .audio_splitter import AudioSplitter
from .transcriber import GeminiTranscriber
from .result_integrator import ResultIntegrator

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        """音声処理クラスの初期化"""
        logger.info("AudioProcessorを初期化中...")
        self.splitter = AudioSplitter()
        self.transcriber = GeminiTranscriber()
        self.integrator = ResultIntegrator()
        logger.info("AudioProcessorの初期化が完了しました")

    def process_audio_file(self, input_file, output_dir, segment_length_seconds=600):
        """
        音声ファイルの分割、文字起こし、結果統合までの一連の処理を実行
        Args:
            input_file (str): 入力音声ファイルのパス
            output_dir (str): 出力ディレクトリのパス
            segment_length_seconds (int): 分割する長さ（秒）
        Returns:
            str: 最終出力ファイルのパス
        """
        try:
            logger.info("=== 音声処理を開始 ===")
            logger.info(f"入力ファイル: {input_file}")
            logger.info(f"出力ディレクトリ: {output_dir}")
            logger.info(f"セグメント長: {segment_length_seconds}秒")

            # 出力ディレクトリの準備
            output_path = Path(output_dir)
            segments_dir = output_path / "segments"
            output_path.mkdir(parents=True, exist_ok=True)
            segments_dir.mkdir(exist_ok=True)
            logger.debug(f"出力ディレクトリを作成/確認: {output_path}")
            logger.debug(f"セグメントディレクトリを作成/確認: {segments_dir}")

            # 音声分割の実行
            logger.info("=== 音声分割処理を開始 ===")
            split_files = self.splitter.split_audio(str(input_file), str(segments_dir))
            logger.info(f"音声を {len(split_files)} 個のセグメントに分割しました")

            # 文字起こしの実行
            logger.info("=== 文字起こし処理を開始 ===")
            all_transcriptions = []
            for i, audio_file in enumerate(split_files, 1):
                logger.info(f"セグメント {i}/{len(split_files)} の文字起こしを実行中...")
                transcription = self.transcriber.transcribe_audio(audio_file)
                
                # セグメント情報を追加
                for conv in transcription["conversations"]:
                    conv["segment"] = i
                    conv["segment_file"] = Path(audio_file).name
                
                all_transcriptions.extend(transcription["conversations"])
                logger.debug(f"セグメント {i} の会話エントリ数: {len(transcription['conversations'])}")

            # 中間結果の保存
            logger.info("=== 中間結果の保存 ===")
            complete_result = {
                "metadata": {
                    "total_segments": len(split_files),
                    "segment_length_seconds": segment_length_seconds,
                    "original_file": str(input_file)
                },
                "conversations": all_transcriptions
            }

            complete_json_path = output_path / "complete_transcription.json"
            logger.info(f"中間結果を保存: {complete_json_path}")
            with open(complete_json_path, "w", encoding="utf-8") as f:
                json.dump(complete_result, f, ensure_ascii=False, indent=2)
            logger.debug(f"合計会話エントリ数: {len(all_transcriptions)}")

            # 最終結果の統合と保存
            logger.info("=== 結果の統合処理を開始 ===")
            final_output = self.integrator.integrate_results(
                str(complete_json_path),
                str(output_path)
            )

            # 一時ファイルのクリーンアップ
            logger.info("=== 一時ファイルのクリーンアップを開始 ===")
            self.integrator.cleanup_temp_files(str(segments_dir))

            logger.info(f"=== 音声処理が完了しました ===")
            logger.info(f"最終結果: {final_output}")
            return final_output

        except Exception as e:
            logger.error(f"音声処理中にエラーが発生しました: {str(e)}", exc_info=True)
            raise 