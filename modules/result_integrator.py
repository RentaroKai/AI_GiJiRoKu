import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class ResultIntegrator:
    def __init__(self):
        """結果統合処理クラスの初期化"""
        logger.info("ResultIntegratorを初期化")

    def integrate_results(self, input_json_path, output_dir):
        """
        complete_transcription.jsonを指定フォーマットのtxtファイルに変換
        Args:
            input_json_path (str): 入力JSONファイルのパス
            output_dir (str): 出力ディレクトリのパス
        Returns:
            str: 出力ファイルのパス
        """
        try:
            logger.info(f"結果統合を開始: {input_json_path}")
            logger.info(f"出力ディレクトリ: {output_dir}")

            # 入力JSONの読み込み
            logger.info("入力JSONファイルを読み込み中...")
            with open(input_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"入力JSONの会話エントリ数: {len(data.get('conversations', []))}")

            # 必要な情報のみを抽出
            logger.info("会話データを整形中...")
            simplified_data = {
                "conversations": [
                    {
                        "speaker": conv["speaker"],
                        "utterance": conv["utterance"]
                    }
                    for conv in data["conversations"]
                ]
            }
            logger.debug(f"整形後の会話エントリ数: {len(simplified_data['conversations'])}")

            # タイムスタンプ付きの出力ファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            output_filename = f"transcription_summary_{timestamp}.txt"
            output_path = Path(output_dir) / output_filename
            logger.debug(f"生成された出力ファイル名: {output_filename}")

            # 結果を保存
            logger.info(f"統合結果を保存中: {output_path}")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(simplified_data, f, ensure_ascii=False, indent=2)

            logger.info(f"統合結果を保存しました: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"結果の統合中にエラーが発生しました: {str(e)}", exc_info=True)
            raise

    def cleanup_temp_files(self, segments_dir):
        """
        一時ファイル（セグメントファイルとその結果）のクリーンアップ
        Args:
            segments_dir (str): セグメントファイルのディレクトリパス
        """
        try:
            logger.info(f"一時ファイルのクリーンアップを開始: {segments_dir}")
            segments_path = Path(segments_dir)
            
            if segments_path.exists():
                # 音声セグメントとJSONファイルを削除
                file_count = 0
                for file in segments_path.glob("*"):
                    if file.suffix in ['.mp3', '.json']:
                        file.unlink()
                        file_count += 1
                        logger.debug(f"一時ファイルを削除: {file}")
                logger.info(f"合計 {file_count} 個の一時ファイルを削除しました")
                
                # 空のディレクトリを削除
                if not any(segments_path.iterdir()):
                    segments_path.rmdir()
                    logger.debug(f"空のセグメントディレクトリを削除: {segments_path}")

            logger.info("一時ファイルのクリーンアップが完了しました")

        except Exception as e:
            logger.error(f"一時ファイルのクリーンアップ中にエラーが発生しました: {str(e)}", exc_info=True)
            raise 