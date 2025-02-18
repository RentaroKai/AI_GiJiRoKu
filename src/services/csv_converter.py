import os
import json
import csv
import logging
import pathlib
from typing import Optional

logger = logging.getLogger(__name__)

class CSVConversionError(Exception):
    """CSV変換関連のエラーを扱うカスタム例外クラス"""
    pass

class CSVConverterService:
    def __init__(self, output_dir: str = "output/csv"):
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def convert_to_csv(self, input_file: pathlib.Path, output_file: Optional[pathlib.Path] = None) -> pathlib.Path:
        """書き起こしテキストをCSVに変換"""
        try:
            logger.info(f"変換処理を開始します: {input_file}")
            
            if not input_file.exists():
                logger.error(f"入力ファイルが見つかりません: {input_file}")
                raise CSVConversionError(f"入力ファイルが見つかりません: {input_file}")
            
            # 出力ファイルパスの設定
            if output_file is None:
                output_file = self.output_dir / f"{input_file.stem}.csv"
            
            # 入力ファイルの読み込み
            with open(input_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # JSONデータの抽出
            json_start = content.find("[")
            json_end = content.rfind("]") + 1
            
            if json_start == -1 or json_end == -1:
                logger.error("JSONデータが見つかりませんでした")
                raise CSVConversionError("JSONデータが見つかりませんでした")
            
            json_str = content[json_start:json_end]
            
            data = []
            try:
                data = json.loads(json_str)
                logger.info(f"JSONデータの読み込みに成功しました。{len(data)}件の会話を検出。")
            except json.JSONDecodeError as e:
                logger.warning(f"標準的なJSONパースに失敗しました。代替手法を試みます: {str(e)}")
                try:
                    # 文字列を整形して再試行
                    cleaned_json = json_str.strip().replace('\n', '').replace('\r', '')
                    # 最後のカンマを削除（一般的なJSON解析エラーの原因）
                    cleaned_json = cleaned_json.rstrip(',]') + ']'
                    data = json.loads(cleaned_json)
                    logger.info(f"クリーニング後のJSONデータの読み込みに成功しました。{len(data)}件の会話を検出。")
                except json.JSONDecodeError:
                    # 正規表現でデータを抽出する最後の手段
                    import re
                    logger.warning("正規表現によるデータ抽出を試みます")
                    pattern = r'"speaker"\s*:\s*"([^"]+)"\s*,\s*"utterance"\s*:\s*"([^"]+)"'
                    matches = re.finditer(pattern, json_str)
                    for match in matches:
                        data.append({
                            "speaker": match.group(1),
                            "utterance": match.group(2)
                        })
                    if data:
                        logger.info(f"正規表現による抽出に成功しました。{len(data)}件の会話を検出。")
                    else:
                        logger.error("データの抽出に失敗しました")
                        raise CSVConversionError("JSONの解析に失敗し、代替手段でもデータを抽出できませんでした")
            
            # CSVファイルの作成
            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerow(["Speaker", "Utterance"])  # ヘッダー行
                
                for record in data:
                    speaker = record.get("speaker", "")
                    utterance = record.get("utterance", "")
                    if speaker and utterance:  # 空のレコードは除外
                        csvwriter.writerow([speaker, utterance])
            
            logger.info(f"CSV変換が完了しました! 出力ファイル: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"変換処理中にエラーが発生しました: {str(e)}")
            raise CSVConversionError(f"変換処理中にエラーが発生しました: {str(e)}")

    def get_output_path(self, input_file: pathlib.Path) -> pathlib.Path:
        """出力ファイルパスの生成"""
        return self.output_dir / f"{input_file.stem}.csv" 