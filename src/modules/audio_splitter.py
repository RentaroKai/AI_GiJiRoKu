import os
from pydub import AudioSegment
from pydub.silence import detect_silence
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
        音声ファイルを指定された長さで分割する（無音検出による自然な区切り）
        事前に全ての分割位置を決定してから分割を実行する
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

            # 理論上の分割位置を計算（例: 0, 300秒, 600秒, ...）
            theoretical_split_points = list(range(0, audio_length_ms, self.segment_length_ms))
            if theoretical_split_points[-1] != audio_length_ms:
                theoretical_split_points.append(audio_length_ms)

            logger.info("理論上の分割位置を計算しました:")
            for i, pos in enumerate(theoretical_split_points):
                logger.info(f"  理論位置 {i+1}: {pos/1000:.2f}秒")

            # 実際の分割位置を決定（無音検出による調整）
            actual_split_points = self._determine_all_split_points(audio, theoretical_split_points)

            logger.info("実際の分割位置を決定しました:")
            for i, (theory, actual) in enumerate(zip(theoretical_split_points, actual_split_points)):
                diff = (actual - theory) / 1000
                logger.info(f"  分割位置 {i+1}: {actual/1000:.2f}秒 (理論位置との差: {diff:.2f}秒)")

            # 分割されたファイルのパスを保存するリスト
            split_files = []

            # 決定した分割位置に基づいて音声を分割
            segment_count = 0
            for i in range(len(actual_split_points) - 1):
                segment_count += 1
                start_ms = actual_split_points[i]
                end_ms = actual_split_points[i + 1]

                logger.info(f"セグメント {segment_count} の処理を開始... (位置: {start_ms/1000:.2f}秒 - {end_ms/1000:.2f}秒)")

                # セグメントを抽出
                segment = audio[start_ms:end_ms]

                # 出力ファイル名を生成
                output_filename = f"segment_{segment_count}.mp3"
                output_path = os.path.join(output_dir, output_filename)

                # セグメントを保存
                segment.export(output_path, format="mp3")
                split_files.append(output_path)

                segment_duration_seconds = (end_ms - start_ms) / 1000
                logger.info(f"セグメント {segment_count} を保存しました: {output_path} (長さ: {segment_duration_seconds:.2f}秒)")

            logger.info(f"音声分割が完了しました。合計 {len(split_files)} 個のセグメントを作成")
            return split_files

        except Exception as e:
            logger.error(f"音声分割中にエラーが発生しました: {str(e)}", exc_info=True)
            raise

    def _determine_all_split_points(self, audio, theoretical_points):
        """
        全ての分割位置を事前に決定する
        Args:
            audio (AudioSegment): 音声データ
            theoretical_points (list): 理論上の分割位置のリスト（ミリ秒）
        Returns:
            list: 実際の分割位置のリスト（ミリ秒）
        """
        actual_points = [theoretical_points[0]]  # 最初の位置（0）は固定

        # 最初と最後以外の各分割位置について、無音検出による調整を行う
        for i in range(1, len(theoretical_points) - 1):
            target_ms = theoretical_points[i]
            actual_point = self._find_optimal_split_point(audio, target_ms)
            actual_points.append(actual_point)

        # 最後の位置は音声の終端で固定
        if len(theoretical_points) > 1:
            actual_points.append(theoretical_points[-1])

        return actual_points

    def _find_optimal_split_point(self, audio, target_ms):
        """
        指定された目標位置周辺で最適な分割ポイント（無音区間）を見つける
        Args:
            audio (AudioSegment): 音声データ
            target_ms (int): 目標となる位置（ミリ秒）
        Returns:
            int: 実際の分割位置（ミリ秒）
        """
        # 無音検出のパラメータ
        min_silence_len = 500  # 最小無音長（ミリ秒）
        silence_thresh = -30   # -40dBから-30dBに変更（より大きな音も「無音」と判定）
        margin_seconds = 10    # 目標時間の前後にどれだけ余裕を持たせるか（秒）- 5秒から10秒に拡大
        margin_ms = margin_seconds * 1000

        # 音声の終端を超えないように調整
        target_ms = min(target_ms, len(audio))

        # 探索範囲（目標位置の前後margin_ms）
        search_start = max(0, target_ms - margin_ms)
        search_end = min(len(audio), target_ms + margin_ms)

        logger.debug(f"無音探索範囲: {search_start/1000:.2f}秒 - {search_end/1000:.2f}秒")

        # 探索範囲が十分でない場合は目標位置で分割
        if search_end - search_start < min_silence_len * 2:
            logger.debug(f"探索範囲が狭すぎるため、目標位置で分割します: {target_ms/1000:.2f}秒")
            return target_ms

        # 探索範囲の音声を抽出
        search_segment = audio[search_start:search_end]

        # まず厳しい閾値で検索し、見つからなければ徐々に寛容な閾値で再検索
        thresholds = [-40, -35, -30, -25]
        for thresh in thresholds:
            silence_ranges = detect_silence(search_segment, min_silence_len=min_silence_len, silence_thresh=thresh)
            if silence_ranges:
                break

        # デバッグ用に検出された無音区間の情報を詳細に出力
        if silence_ranges:
            logger.debug(f"検出された無音区間: {len(silence_ranges)}個")
            for i, (start, end) in enumerate(silence_ranges):
                logger.debug(f"  無音区間 {i+1}: {start/1000:.2f}秒 - {end/1000:.2f}秒 (長さ: {(end-start)/1000:.2f}秒)")

        # 無音区間が見つからない場合は音量が最も小さい位置を探索
        if not silence_ranges:
            logger.info(f"{target_ms/1000:.2f}秒付近に無音区間が見つかりません。音量が最小の位置を探索します...")
            min_volume_position = self._find_min_volume_position(search_segment)
            actual_split_point = search_start + min_volume_position
            logger.info(f"最小音量位置で分割します: {actual_split_point/1000:.2f}秒")
            return actual_split_point

        # 目標位置に最も近い無音区間を選択
        best_position = self._select_best_silence(silence_ranges, target_ms - search_start)

        # 実際の分割位置（絶対位置）
        actual_split_point = search_start + best_position
        logger.info(f"{target_ms/1000:.2f}秒付近で無音区間を検出しました: {actual_split_point/1000:.2f}秒 (目標との差: {(actual_split_point-target_ms)/1000:.2f}秒)")

        return actual_split_point

    def _select_best_silence(self, silence_ranges, target_position):
        """
        複数の無音区間から目標位置に最も近いものを選択する
        Args:
            silence_ranges (list): 無音区間のリスト [(start, end), ...]
            target_position (int): 目標位置（探索範囲の開始位置からの相対位置）
        Returns:
            int: 選択された無音区間の中央位置（探索範囲の開始位置からの相対位置）
        """
        best_distance = float('inf')
        best_position = target_position

        for start, end in silence_ranges:
            # 無音区間の中央位置
            mid_position = (start + end) // 2

            # 目標位置との距離
            distance = abs(mid_position - target_position)

            if distance < best_distance:
                best_distance = distance
                # 無音区間の中央位置を使用
                best_position = mid_position

        return best_position

    def _find_min_volume_position(self, audio_segment):
        """
        音声セグメント内で最も音量が小さい位置を見つける

        Args:
            audio_segment (AudioSegment): 探索対象の音声セグメント

        Returns:
            int: 最小音量位置（ミリ秒、セグメント開始位置からの相対位置）
        """
        # 音量分析のためのウィンドウサイズ（ミリ秒）
        window_size = 100

        # 音量が最小の位置と値を保持する変数
        min_volume = float('inf')
        min_position = 0

        # セグメントを小さな区間に分けて音量を計算
        for i in range(0, len(audio_segment) - window_size, window_size):
            # 現在のウィンドウを取得
            window = audio_segment[i:i+window_size]
            # ウィンドウの音量（RMS）を計算
            volume = window.rms

            # より小さい音量が見つかった場合、位置と値を更新
            if volume < min_volume:
                min_volume = volume
                min_position = i + window_size // 2

        return min_position