import os
import json
import csv
import logging
import pathlib
import re
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class CSVConversionError(Exception):
    """CSV変換関連のエラーを扱うカスタム例外クラス"""
    pass

class CSVConverterService:
    def __init__(self, output_dir: str = "output/csv"):
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _clean_text(self, text: str) -> str:
        """テキストのクリーニング処理"""
        # 基本的な特殊文字の削除
        text = re.sub(r'["\\\{\}]', '', text)
        # 制御文字の削除
        text = re.sub(r'[\x00-\x1F\x7F]', '', text)
        # 全角スペースを半角に
        text = text.replace('　', ' ')
        # 複数の空白を1つに
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_conversations(self, content: str) -> List[Dict[str, str]]:
        """テキストから会話データを抽出"""
        conversations = []
        
        # より柔軟な正規表現パターン
        pattern = r'(?:"speaker"|speaker)\s*:?\s*"?([^",}\n]+)"?\s*,?\s*(?:"utterance"|utterance)\s*:?\s*"?([^"}\n][^}\n]*[^",}\n])"?'
        
        logger.debug(f"テキストの抽出を開始します。テキスト長: {len(content)}")
        
        # マルチラインで検索
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        match_count = 0

        for match in matches:
            match_count += 1
            speaker = self._clean_text(match.group(1))
            utterance = self._clean_text(match.group(2))

            # バリデーション
            if not speaker or not utterance:
                logger.warning(f"空の発話者または発話を検出: speaker='{speaker}', utterance='{utterance}'")
                continue
                
            if len(speaker) > 100:
                logger.warning(f"異常に長い発話者名を検出: {speaker[:50]}...")
                continue

            if len(utterance) < 2:
                logger.warning(f"異常に短い発話を検出: {utterance}")
                continue

            conversations.append({
                "speaker": speaker,
                "utterance": utterance
            })

        logger.info(f"抽出結果: 全{match_count}件中、有効な会話{len(conversations)}件")
        return conversations

    def convert_to_csv(self, input_file: pathlib.Path, output_file: Optional[pathlib.Path] = None) -> pathlib.Path:
        """書き起こしテキストをCSVに変換"""
        try:
            logger.info(f"変換処理を開始します: {input_file}")

            if not input_file.exists():
                error_msg = f"入力ファイルが見つかりません: {input_file}"
                logger.error(error_msg)
                raise CSVConversionError(error_msg)

            # 出力ファイルパスの設定
            if output_file is None:
                output_file = self.output_dir / f"{input_file.stem}.csv"

            # 入力ファイルの読み込み
            with open(input_file, "r", encoding="utf-8") as f:
                content = f.read()
                logger.debug(f"ファイル読み込み完了。サイズ: {len(content)}バイト")

            data = []
            try:
                # まずJSONとしてパースを試みる
                json_data = json.loads(content)
                if isinstance(json_data, dict) and "conversations" in json_data:
                    data = json_data["conversations"]
                    logger.info("会話データをJSONオブジェクトから抽出しました")
                elif isinstance(json_data, list):
                    data = json_data
                    logger.info("会話データをJSON配列から抽出しました")
                logger.info(f"JSONデータの読み込みに成功しました。{len(data)}件の会話を検出")
            except json.JSONDecodeError as e:
                logger.warning(f"JSONパースに失敗: {str(e)}。テキストベースの抽出を試みます")
                # テキストベースの抽出を実行
                data = self._extract_conversations(content)
                if data:
                    logger.info(f"テキストベースの抽出に成功しました。{len(data)}件の会話を検出")
                else:
                    logger.warning("テキストベースの抽出でも会話が見つかりませんでした")

            if not data:
                error_msg = "有効な会話データが見つかりませんでした"
                logger.error(error_msg)
                raise CSVConversionError(error_msg)

            # CSVファイルの作成 - BOM付きUTF-8で保存
            with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerow(["Speaker", "Utterance"])  # ヘッダー行

                valid_records = 0
                for record in data:
                    speaker = record.get("speaker", "").strip()
                    utterance = record.get("utterance", "").strip()
                    if speaker and utterance:  # 空のレコードは除外
                        csvwriter.writerow([speaker, utterance])
                        valid_records += 1

            logger.info(f"CSV変換が完了しました! 出力ファイル: {output_file}, 有効レコード数: {valid_records}")
            return output_file

        except Exception as e:
            error_msg = f"変換処理中にエラーが発生しました: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise CSVConversionError(error_msg)

    def get_output_path(self, input_file: pathlib.Path) -> pathlib.Path:
        """出力ファイルパスの生成"""
        return self.output_dir / f"{input_file.stem}.csv" 