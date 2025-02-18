# AI議事録作成アプリ（GiJiRoKu）

会議や講演の音声/動画ファイルから自動的に議事録を作成するAI議事録君です。
pythonとか分からないという人は　exeファイルをこちらからDLして使ってください。


## 🌟 主な機能

- 音声/動画ファイルからテキストへの自動変換
- AIによる議事録の自動生成
- カスタマイズ可能なプロンプト設定
- 簡単な操作で高品質な議事録を作成

## 🔧 必要要件

- Windows 10以上
- FFmpeg（アプリケーションに同梱）
- Python 3.8以上（実行ファイルを使用する場合は不要）

## 📦 必要なパッケージ

- openai
- pydantic (>=2.0.0)
- pydub (>=0.25.1)
- pyperclip (>=1.8.2)
- typing-extensions (>=4.0.0)
- requests (>=2.31.0)
- ffmpeg-python (>=0.2.0)

## 🚀 はじめる前に

###  OpenAI APIキーの取得

このアプリを使用するには、OpenAIのAPIキーが必要です。以下の手順で取得できます：

1. [OpenAIのウェブサイト](https://platform.openai.com/signup)にアクセスし、アカウントを作成
2. ログイン後、https://platform.openai.com/api-keys　にアクセス
3. 「Create new secret key」をクリックして新しいAPIキーを作成
4. 作成されたAPIキーを設定画面から入力するか、環境変数「OPENAI_API_KEY」に設定してください。

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

ビルドされたアプリケーションは `dist` ディレクトリに生成されます。