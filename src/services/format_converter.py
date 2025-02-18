import subprocess
import os

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
        return True
    return False


def get_output_filename(input_file, target_ext='mp3'):
    """
    入力ファイルパスから変換後のファイル名を生成する関数
    """
    base, _ = os.path.splitext(input_file)
    output_file = f"{base}_converted.{target_ext}"
    return output_file


def convert_file(input_file):
    """
    入力ファイルをFFmpegを利用して変換し、変換後のファイルパスを返す。
    変換対象のファイルが未対応フォーマットの場合のみ変換処理を実施し、
    それ以外の場合は入力ファイルパスをそのまま返す。
    """
    # 未対応フォーマットの場合、変換処理を実施
    if not is_conversion_needed(input_file):
        print("変換は不要。既に対応している形式です。")
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
        print("未知の形式のため変換スキップ")
        return input_file

    print(f"変換開始: {cmd}")
    
    # コマンドプロンプトで実行するため、shell=Trueを指定
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        # FFmpegの出力内容をログに出力
        print("標準出力:", result.stdout)
        print("標準エラー出力:", result.stderr)
        
        if result.returncode != 0:
            print(f"FFmpegエラー: returncode {result.returncode}")
            raise Exception(f"FFmpegによる変換が失敗しました。: {result.stderr}")
        else:
            print("変換に成功しました。")
    except Exception as e:
        print("変換処理中にエラーが発生しました:", str(e))
        raise e

    # 変換成功時、変換後のファイルパスを返す
    return output_file


def cleanup_file(file_path):
    """
    変換後の一時ファイルを削除する関数
    """
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"{file_path} の削除に成功しました。")
        except Exception as e:
            print(f"{file_path} の削除に失敗しました: {str(e)}")
    else:
        print(f"{file_path} は存在しません。")


if __name__ == '__main__':
    # テスト実行用のコード
    import sys
    if len(sys.argv) < 2:
        print("使用方法: python format_converter.py 入力ファイルパス")
        sys.exit(1)
    
    input_path = sys.argv[1]
    print(f"入力ファイル: {input_path}")
    
    try:
        converted = convert_file(input_path)
        print(f"変換後のファイル: {converted}")
    except Exception as err:
        print("エラーが発生しました:", err) 