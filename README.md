# AI議事録作成アプリ（GiJiRoKu）

会議や講演の音声/動画ファイルから自動的に議事録を作成するAI議事録君です。

## 🌟 主な機能

- 音声/動画ファイルからテキストへの自動変換
- AIによる議事録の自動生成
- カスタマイズ可能なプロンプト設定

## 🚀 はじめる前に

###  OpenAI APIキーの取得

このアプリは無料で利用できますが、使用するには、OpenAIのAPIキーが必要です。最初の５ドル分無料で、以後は使った量に応じて費用がかかります(安いです)。以下の手順で取得できます：

1. [OpenAIのウェブサイト](https://platform.openai.com/signup)にアクセスし、アカウントを作成  
2. ログイン後、https://platform.openai.com/api-keys
　にアクセス  
3. 「Create new secret key」をクリックして新しいAPIキーを作成
4. 作成されたAPIキーを設定画面から入力するか、環境変数「OPENAI_API_KEY」に設定してください。


## 🚀 使い方（かんたん版）

#### Step 1: アプリの準備
1. [リリースページ](https://github.com/RentaroKai/AI_GiJiRoKu/releases)から最新の「GiJiRoKu.exe」をダウンロードします
2. ダウンロードしたファイルを好きな場所に保存します

#### Step 2: アプリの起動
1. 保存した「GiJiRoKu.exe」をダブルクリックして起動します
2. 初回起動時は、OpenAI APIキーの設定が必要です
   - 上記の「はじめる前に」セクションを参考にAPIキーを取得してください

#### Step 3: 音声/動画ファイルの準備
1. 議事録にしたい会議や講演の音声/動画ファイルを用意します
2. 対応しているファイル形式：
   - 音声：mp3, wav, m4a, aac, flac, ogg
   - 動画：mkv, avi, mov, flv

#### Step 4: 議事録の作成
1. アプリの「参照」ボタンをクリックします
2. 用意した音声/動画ファイルを選択します
3. 「実行」ボタンをクリックします
4. しばらく待つと自動で議事録が作成されます

#### Step 5: 議事録の確認と保存
作成された議事録は自動的に保存されます
📁ボタンを押すと出てきます
拡張子はいろいろですが、全部、メモ帳アプリで開けます

### ⚠️ 注意事項
- インターネット接続が必要です
- APIキーの利用には料金が発生します（安いです）
- 音声認識は完全ではありません。重要な会議では、作成された議事録の内容を必ず確認してください


## 🔧 必要要件

- Windows 10以上
- Python 3.8以上（実行ファイルを使用する場合は不要）

## 📦 必要なパッケージ

- openai
- pydantic (>=2.0.0)
- pydub (>=0.25.1)
- pyperclip (>=1.8.2)
- typing-extensions (>=4.0.0)
- requests (>=2.31.0)
- ffmpeg-python (>=0.2.0)



## 📂 プロジェクト構造

- `src/` - ソースコードディレクトリ
- `resources/` - リソースファイル（FFmpegなど）
- `config/` - 設定ファイル
- `output/` - 生成された議事録の出力先
- `logs/` - ログファイル

## 🛠️ ビルド方法

```bash
pyinstaller GiJiRoKu.spec
```

## 🎯 プロンプトのカスタマイズ

`src/prompts/` ディレクトリ内の以下のファイルを編集することで、AIの動作をカスタマイズできます：

- `minutes.txt`: 議事録の作成方法と形式
- `reflection.txt`: 会議の振り返り分析の基準
- `transcription.txt`: 音声の書き起こし整形ルール



## 📝 ライセンス情報

### GiJiRoKu
MIT License

### FFmpeg
このソフトウェアは、FFmpeg（https://ffmpeg.org/）を使用しています。
FFmpegは以下のライセンスの下で提供されています：

- GNU Lesser General Public License (LGPL) version 2.1以降
- GNU General Public License (GPL) version 2以降

FFmpegのソースコードは以下から入手可能です：
https://ffmpeg.org/download.html

FFmpegは以下の著作権表示が必要です：
```
This software uses code of FFmpeg (http://ffmpeg.org) licensed under the LGPLv2.1 and its source can be downloaded from https://ffmpeg.org/
```
