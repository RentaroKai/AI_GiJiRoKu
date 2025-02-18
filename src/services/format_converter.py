import subprocess
import os
import logging

logger = logging.getLogger(__name__)

class FormatConversionError(Exception):
    """フォーマット変換関連のエラーを扱うカスタム例外クラス"""
    pass

# 未対応フォーマットの拡張子リスト
AUDIO_FORMATS = ['m4a', 'aac', 'flac', 'ogg']
VIDEO_FORMATS = ['mkv', 'avi', 'mov', 'flv']


def is_conversion_needed(file_path):
    """
    ファイルの拡張子から変換が必要かどうか判断する関数
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower().lstrip('.')
    if ext in AUDIO_FORMATS or ext in VIDEO_FORMATS:
        logger.info(f"ファイル {file_path} は変換が必要です（形式: {ext}）")
        return True
    logger.info(f"ファイル {file_path} は変換不要です（形式: {ext}）")
    return False


def get_output_filename(input_file, target_ext='mp3'):
    """
    入力ファイルパスから変換後のファイル名を生成する関数
    """
    base, _ = os.path.splitext(input_file)
    output_file = f"{base}_converted.{target_ext}"
    logger.debug(f"変換後のファイル名を生成: {output_file}")
    return output_file


def convert_file(input_file):
    """
    入力ファイルをFFmpegを利用して変換し、変換後のファイルパスを返す。
    変換対象のファイルが未対応フォーマットの場合のみ変換処理を実施し、
    それ以外の場合は入力ファイルパスをそのまま返す。
    """
    logger.info(f"ファイル変換処理を開始: {input_file}")
    
    # 未対応フォーマットの場合、変換処理を実施
    if not is_conversion_needed(input_file):
        logger.info("変換は不要。既に対応している形式です。")
        return input_file

    # 変換先のファイル名生成
    output_file = get_output_filename(input_file, target_ext='mp3')

    # 入力ファイルの拡張子を取得
    _, ext = os.path.splitext(input_file)
    ext = ext.lower().lstrip('.')

    # FFmpegのコマンド作成
    if ext in AUDIO_FORMATS:
        # オーディオの場合の変換コマンド
        cmd = f'ffmpeg -y -i "{input_file}" "{output_file}"'
    elif ext in VIDEO_FORMATS:
        # 動画の場合の変換コマンド（動画部分を除外）
        cmd = f'ffmpeg -y -i "{input_file}" -vn -acodec mp3 "{output_file}"'
    else:
        # その他の形式の場合はそのまま返す（通常はここに到達しない）
        logger.warning(f"未知の形式のため変換をスキップ: {ext}")
        return input_file

    logger.info(f"変換開始: {cmd}")
    
    # コマンドプロンプトで実行するため、shell=Trueを指定
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        # FFmpegの出力内容をログに出力
        logger.debug("FFmpeg標準出力: %s", result.stdout)
        logger.debug("FFmpeg標準エラー出力: %s", result.stderr)
        
        if result.returncode != 0:
            error_msg = f"FFmpegエラー: returncode {result.returncode}"
            logger.error(error_msg)
            logger.error("FFmpegエラー詳細: %s", result.stderr)
            raise FormatConversionError(f"FFmpegによる変換が失敗しました。: {result.stderr}")
        else:
            logger.info("変換に成功しました。")
    except subprocess.SubprocessError as e:
        error_msg = f"FFmpegの実行中にエラーが発生: {str(e)}"
        logger.error(error_msg)
        raise FormatConversionError(error_msg)
    except Exception as e:
        error_msg = f"変換処理中に予期せぬエラーが発生: {str(e)}"
        logger.error(error_msg)
        raise FormatConversionError(error_msg)

    # 変換後のファイルが存在することを確認
    if not os.path.exists(output_file):
        error_msg = f"変換後のファイルが見つかりません: {output_file}"
        logger.error(error_msg)
        raise FormatConversionError(error_msg)

    logger.info(f"変換処理が完了しました: {output_file}")
    return output_file


def cleanup_file(file_path):
    """
    変換後の一時ファイルを削除する関数
    """
    logger.info(f"一時ファイルの削除を開始: {file_path}")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"{file_path} の削除に成功しました。")
        except Exception as e:
            error_msg = f"{file_path} の削除に失敗: {str(e)}"
            logger.error(error_msg)
            raise FormatConversionError(error_msg)
    else:
        logger.warning(f"{file_path} は存在しません。")


if __name__ == '__main__':
    # テスト実行用のコード
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        logger.error("使用方法: python format_converter.py 入力ファイルパス")
        sys.exit(1)
    
    input_path = sys.argv[1]
    logger.info(f"入力ファイル: {input_path}")
    
    try:
        converted = convert_file(input_path)
        logger.info(f"変換後のファイル: {converted}")
    except FormatConversionError as e:
        logger.error(f"変換エラー: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"予期せぬエラー: {str(e)}")
        sys.exit(1) 