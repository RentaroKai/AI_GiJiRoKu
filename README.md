# AI議事録作成アプリ（GiJiRoKu）

会議や講演の音声/動画ファイルから自動的に議事録を作成するAI議事録君です。

## 🌟 主な機能

- 音声/動画ファイルからテキストへの自動変換
- AIによる議事録の自動生成
- カスタマイズ可能なプロンプト設定

## 🚀 はじめる前に

このアプリは無料で利用できますが、使用するには、OpenAIのAPIキーが必要です。

###  OpenAI APIキーの取得

最初の５ドル分無料で、以後は使った量に応じて費用がかかります(安いです)。以下の手順で取得できます：

1. [OpenAIのウェブサイト](https://platform.openai.com/signup)にアクセスし、アカウントを作成  
2. ログイン後、https://platform.openai.com/api-keys
　にアクセス  
3. 「Create new secret key」をクリックして新しいAPIキーを作成
4. 作成されたAPIキーを設定画面から入力するか、環境変数「OPENAI_API_KEY」に設定してください。

###  GOOGLE APIキーの取得

任意で、無料のGOOGLE(GEMINI)のAPIキーも使えます。
OPENAIのAPIキーは原則として必須ですが、書き起こしだけGOOGLEのAPIキーを使うことが可能です。使いたくない場合はAPIキーを登録しなければ使わないで済みます。

1. [GOOGLEのウェブサイト](https://aistudio.google.com/app/apikey)でAPIキーを作成
2. 作成されたAPIキーを設定画面から入力するか、環境変数「GOOGLE_API_KEY」に設定してください。
3. 設定→書き起こし方式　で　「Gemini方式」　を選択する


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
1. アプリの「ファイル選択」ボタンをクリックします
2. 用意した音声/動画ファイルを選択します
3. 必要に応じて以下のオプションをチェックします：
   - 「議事録作成」: AIによる議事録の生成
   - 「会議の反省点」: 会議の振り返り分析の生成
   （音声の書き起こしは常に実行されます）
4. 「実行」ボタンをクリックします
5. しばらく待つと選択したオプションに応じた文書が作成されます

#### Step 5: 議事録の確認と保存

作成された議事録は自動的に保存されます  
📁 ボタンを押すと出てきます  
 
議事録は Markdown 形式（.md）で保存されています。表示がうまくいかない、または操作に不慣れな場合は、メモ帳（Notepad）などのシンプルなテキストエディタで開くようにしてください。

### ⚠️ 注意事項
- インターネット接続が必要です
- GOOGLEの無料APIキーは学習に使われます。社外秘には使わないようにしたほうがいいです。
- 音声認識は完全ではありません。重要な会議では、作成された議事録の内容を必ず確認してください


## 🔧 必要要件

- Windows 10以上
- Python 3.9以上（exeファイルを使用する場合は不要）

## 📦 必要なパッケージ

- openai (>=1.12.0)
- pydantic (>=2.6.1)
- pydub (>=0.25.1)
- pyperclip (>=1.8.2)
- typing-extensions (>=4.9.0)
- requests (>=2.31.0)
- ffmpeg-python (>=0.2.0)
- google-generativeai (>=0.3.2)
- python-dotenv (>=1.0.0)



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

## 🎯 カスタマイズのやり方

`src/prompts/` ディレクトリ内の以下のファイルを編集することで、AIの動作をカスタマイズできます：

- `minutes.txt`: 議事録の作成方法と形式
- `reflection.txt`: 会議の振り返り分析の基準
- `transcription.txt`: 音声の書き起こし整形ルール
- `transcriptionGEMINI.txt`: 音声の書き起こし整形ルール（GEMINI方式）

`src/utils/` ディレクトリ内の以下のファイルを編集することで、AIのモデルを指定できます：

- `Common_OpenAIAPI.py`: openAIのモデルの指定を変えられます DEFAULT_CHAT_MODEL = "XXX"の部分をかえることもできます。

- `gemini_api.py`: geminiのモデルの指定を変えられます model_name="XXX"を書き換えるとモデルが変更できます。最大文字数も増やせます。

## ⚙️ 設定画面の使い方

設定画面では、議事録作成の細かい部分を自分好みにカスタマイズできます。
主な設定項目を分かりやすく説明します：

### 📝 基本設定

#### APIキー設定
- **OpenAI APIキー**: 必須。ここに入れるか、環境変数「OPENAI_API_KEY」に設定してください。
- **Google APIキー**: GEMINI方式での書き起こしに使用します（任意）。ここに入れるか、環境変数「GOOGLE_API_KEY」に設定してください。

#### 書き起こし方式の選択
- **Whisper方式**: OpenAIの高精度な音声認識を使用（安い・クオリティ低い）
- **GPT-4 Audio方式**: OpenAIの高精度な音声認識を使用（10分30円くらい・クオリティ高い）
- **Gemini方式**: Googleの無料APIを使用（めちゃくちゃ安い・クオリティ高い）

#### 分割処理用の秒数
- **推奨値**: 300秒
- **この設定が必要な理由**: 
  - 長い音声を一度に処理するとAIが性能的に処理しきれず不安定になるため、適度な長さに分けて処理します
  - 短すぎると話者の判定がぐちゃぐちゃになり、長すぎると文字起こしが不安定になります
  - whisper方式は現在は分割していませんので関係ありません

#### 出力ディレクトリ
- 議事録の出力先を指定できます。




## 📝 ライセンス情報

### AI_GiJiRoKu
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
