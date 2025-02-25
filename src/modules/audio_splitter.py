import os
from pydub import AudioSegment
import logging

logger = logging.getLogger(__name__)

class AudioSplitter:
    def __init__(self, segment_length_seconds=600):
        """
        音声分割クラスの初期化
        Args:
            segment_length_seconds (int): 分割する長さ（秒）
        """
        self.segment_length_seconds = segment_length_seconds
        self.segment_length_ms = segment_length_seconds * 1000
        logger.info(f"AudioSplitterを初期化: セグメント長 = {segment_length_seconds}秒 ({self.segment_length_ms}ミリ秒)")

    def split_audio(self, input_file_path, output_dir):
        """
        音声ファイルを指定された長さで分割する
        Args:
            input_file_path (str): 入力音声ファイルのパス
            output_dir (str): 出力ディレクトリのパス
        Returns:
            list: 分割された音声ファイルのパスのリスト
        """
        try:
            logger.info(f"音声分割を開始: {input_file_path}")
            logger.info(f"出力ディレクトリ: {output_dir}")

            # 出力ディレクトリが存在しない場合は作成
            os.makedirs(output_dir, exist_ok=True)

            # 音声ファイルを読み込む
            logger.info("音声ファイルを読み込み中...")
            audio = AudioSegment.from_file(input_file_path)
            audio_length_ms = len(audio)
            audio_length_seconds = audio_length_ms / 1000
            logger.info(f"音声ファイルを読み込みました: 長さ = {audio_length_seconds:.2f}秒")
            
            # 分割されたファイルのパスを保存するリスト
            split_files = []
            total_segments = (audio_length_ms + self.segment_length_ms - 1) // self.segment_length_ms
            logger.info(f"予想セグメント数: {total_segments}")
            
            # 音声を指定された長さで分割
            for i, start_ms in enumerate(range(0, len(audio), self.segment_length_ms), 1):
                logger.info(f"セグメント {i}/{total_segments} の処理を開始...")
                
                # 終了位置を計算
                end_ms = min(start_ms + self.segment_length_ms, len(audio))
                
                # セグメントを抽出
                segment = audio[start_ms:end_ms]
                
                # 出力ファイル名を生成
                output_filename = f"segment_{i}.mp3"
                output_path = os.path.join(output_dir, output_filename)
                
                # セグメントを保存
                segment.export(output_path, format="mp3")
                split_files.append(output_path)
                logger.info(f"セグメント {i}/{total_segments} を保存しました: {output_path}")
                
                # 最後のセグメントなら終了
                if end_ms >= len(audio):
                    break
            
            logger.info(f"音声分割が完了しました。合計 {len(split_files)} 個のセグメントを作成")
            return split_files

        except Exception as e:
            logger.error(f"音声分割中にエラーが発生しました: {str(e)}", exc_info=True)
            raise 