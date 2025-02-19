import os
import pathlib
import subprocess
import tempfile
import logging
import time
import sys
from pydub import AudioSegment
from typing import Tuple

logger = logging.getLogger(__name__)

class AudioProcessingError(Exception):
    """音声処理関連のエラーを扱うカスタム例外クラス"""
    pass

class AudioProcessor:
    def __init__(self, target_file_size: int = 25000000):  # 25MB
        self.target_file_size = target_file_size
        self.temp_dir = pathlib.Path(tempfile.gettempdir()) / "GiJiRoKu"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"一時ディレクトリを作成しました: {self.temp_dir}")
        logger.info(f"一時ディレクトリの権限: {oct(os.stat(self.temp_dir).st_mode)[-3:]}")

        # PyInstallerのリソースパスを取得
        if getattr(sys, 'frozen', False):
            # PyInstallerで実行している場合
            base_path = pathlib.Path(sys._MEIPASS)
            logger.info(f"PyInstaller実行モード - MEIPASS: {base_path}")
            self.ffmpeg_dir = base_path / "resources/ffmpeg"
        else:
            # 通常の実行の場合
            logger.info("通常実行モード")
            self.ffmpeg_dir = pathlib.Path("resources/ffmpeg")

        logger.info(f"FFmpegディレクトリ: {self.ffmpeg_dir}")

        self.ffmpeg_path = self.ffmpeg_dir / "ffmpeg.exe"
        self.ffprobe_path = self.ffmpeg_dir / "ffprobe.exe"

        # FFmpegの存在確認と詳細ログ
        if self.ffmpeg_path.exists():
            logger.info(f"FFmpeg実行ファイルを確認: {self.ffmpeg_path}")
            logger.info(f"FFmpegファイルサイズ: {self.ffmpeg_path.stat().st_size:,} bytes")
            logger.info(f"FFmpeg権限: {oct(os.stat(self.ffmpeg_path).st_mode)[-3:]}")
        else:
            logger.error(f"FFmpegの実行ファイルが見つかりません: {self.ffmpeg_path}")
            logger.error(f"現在のディレクトリ: {os.getcwd()}")
            logger.error(f"ディレクトリ内容: {list(self.ffmpeg_dir.parent.glob('**/*'))}")
            raise AudioProcessingError(f"FFmpegの実行ファイルが見つかりません: {self.ffmpeg_path}")

        # FFmpegのパスを環境変数に追加
        os.environ["PATH"] = str(self.ffmpeg_path.parent) + os.pathsep + os.environ["PATH"]
        logger.info("FFmpegを環境変数PATHに追加しました")

    def cleanup_temp_files(self, max_age_hours: int = 24) -> None:
        """一時ファイルのクリーンアップ"""
        try:
            current_time = time.time()
            logger.info(f"一時ファイルのクリーンアップを開始: {self.temp_dir}")

            for temp_file in self.temp_dir.glob("*"):
                file_age = current_time - temp_file.stat().st_mtime
                logger.debug(f"一時ファイルをチェック: {temp_file} (経過時間: {file_age/3600:.1f}時間)")
                if file_age > max_age_hours * 3600:
                    logger.info(f"古い一時ファイルを削除: {temp_file}")
                    temp_file.unlink()

            logger.info("一時ファイルのクリーンアップが完了しました")
        except Exception as e:
            logger.error(f"一時ファイルのクリーンアップ中にエラーが発生しました: {str(e)}")

    def extract_audio(self, input_file: pathlib.Path) -> Tuple[pathlib.Path, bool]:
        """音声の抽出と必要に応じた圧縮を行う"""
        try:
            logger.info(f"音声ファイルの処理を開始: {input_file}")
            logger.info(f"入力ファイルサイズ: {input_file.stat().st_size:,} bytes")
            logger.info(f"入力ファイルの権限: {oct(os.stat(input_file).st_mode)[-3:]}")

            # 一時ファイルのパスを生成
            temp_audio = self.temp_dir / f"temp_audio_{os.urandom(4).hex()}{input_file.suffix}"
            logger.info(f"一時音声ファイルを作成: {temp_audio}")

            # 音声の抽出
            logger.info("FFmpegで音声抽出を開始")
            cmd = [str(self.ffmpeg_path), "-y", "-i", str(input_file), "-codec:a", "copy", "-vn", str(temp_audio)]
            logger.debug(f"FFmpegコマンド: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )

            if result.stderr:
                logger.debug(f"FFmpeg stderr出力: {result.stderr}")

            # ファイルサイズのチェック
            temp_size = temp_audio.stat().st_size
            logger.info(f"抽出された音声ファイルサイズ: {temp_size:,} bytes")

            if temp_size <= self.target_file_size:
                logger.info("音声ファイルのサイズは制限内です")
                return temp_audio, False

            # 圧縮が必要な場合
            logger.info(f"音声ファイルの圧縮を開始します（目標サイズ: {self.target_file_size:,} bytes）")
            audio_segment = AudioSegment.from_file(str(temp_audio))
            audio_length_sec = len(audio_segment) / 1000
            target_kbps = int(self.target_file_size * 8 / audio_length_sec / 1000 * 0.95)

            logger.info(f"音声長: {audio_length_sec:.1f}秒")
            logger.info(f"目標ビットレート: {target_kbps}kbps")

            if target_kbps < 8:
                logger.error(f"必要なビットレートが低すぎます: {target_kbps}kbps")
                raise AudioProcessingError("必要なビットレートが低すぎます")

            compressed_audio = self.temp_dir / f"compressed_audio_{os.urandom(4).hex()}.mp3"
            logger.info(f"圧縮音声ファイルを作成: {compressed_audio}")

            cmd = [str(self.ffmpeg_path), "-y", "-i", str(temp_audio),
                  "-codec:a", "libmp3lame", "-ar", "22050", "-ac", "1",
                  "-q:a", "4", "-b:a", f"{target_kbps}k",
                  str(compressed_audio)]
            logger.debug(f"FFmpeg圧縮コマンド: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )

            if result.stderr:
                logger.debug(f"FFmpeg圧縮stderr出力: {result.stderr}")

            # 元の一時ファイルを削除
            logger.info(f"元の一時ファイルを削除: {temp_audio}")
            temp_audio.unlink()

            compressed_size = compressed_audio.stat().st_size
            logger.info(f"圧縮後のファイルサイズ: {compressed_size:,} bytes")
            logger.info(f"圧縮率: {(1 - compressed_size/temp_size) * 100:.1f}%")

            return compressed_audio, True

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpegエラー: {e.stderr}")
            logger.error(f"FFmpegコマンド: {e.cmd}")
            logger.error(f"FFmpeg終了コード: {e.returncode}")
            raise AudioProcessingError(f"FFmpeg処理に失敗しました: {e.stderr}")
        except Exception as e:
            logger.error(f"音声処理エラー: {str(e)}")
            logger.error(f"エラータイプ: {type(e).__name__}")
            raise AudioProcessingError(f"音声処理に失敗しました: {str(e)}")

    def __del__(self):
        """デストラクタでの一時ファイルクリーンアップ"""
        try:
            logger.info("デストラクタでの一時ファイルクリーンアップを開始")
            self.cleanup_temp_files()
        except Exception as e:
            logger.error(f"デストラクタでのクリーンアップ中にエラーが発生しました: {str(e)}")