# AI Meeting Minutes App (GiJiRoKu)

This is an AI-powered app that automatically creates meeting minutes from audio/video files of meetings or lectures.

## 🌟 Main Features

- Transcribe conversations from audio/video files to create meeting minutes
- Automatically generate a summary of the minutes (customizable)

## 🚀 Easy Usage

#### Step 1: Download
1. Download the latest "GiJiRoKu.exe" from the [release page](https://github.com/RentaroKai/AI_GiJiRoKu/releases)
2. Save it to your preferred location

#### Step 2: Launch
1. Double-click "GiJiRoKu.exe" to launch
   *Note: On first launch, Windows Defender SmartScreen may display a warning. Click "More info" and then select the "Run" button.*
2. On the first launch, you need to set up the API key (details below)

#### Step 3: Select File
1. Click the "Select File" button
2. Choose the audio/video file you want to convert into minutes
   - Supported formats: Audio (mp3, wav, m4a, aac, flac, ogg), Video (mkv, avi, mov, flv)

#### Step 4: Execute
1. Optionally deselect options as needed
   - "Create Minutes": Generate a summary of the minutes using AI
2. Click the "Execute" button

#### Step 5: Check Results
The created minutes are automatically saved and can be checked with the 📁 button.

## 🔑 Setting Up API Keys

This app requires either an OpenAI API key or a Gemini API key (only one is needed).

### OpenAI API Key
1. Create an account on the [OpenAI website](https://platform.openai.com/signup)
2. Click "Create new secret key" on the [API key page](https://platform.openai.com/api-keys)
3. Enter the created API key in the app's settings screen or set it as the environment variable "OPENAI_API_KEY"

### Google API Key (for Gemini method)
1. Create an API key on [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Enter the created API key in the app's settings screen or set it as the environment variable "GOOGLE_API_KEY"

## ⚙️ Using the Settings Screen

In the settings screen, accessible via the settings button, you can customize the details of the meeting minutes creation.

### 📝 Basic Settings Tab

#### API Key Settings
- **OpenAI API Key**: Required for using Whisper or GPT-4 Audio methods
- **Google API Key**: Required for using the Gemini method

#### Selection of Processing Method
- **Transcription Method**:
  - **Whisper Method**: OpenAI's speech recognition (low cost, lower quality)
  - **GPT-4 Audio Method**: OpenAI's high-precision speech recognition (approx. 30 yen for 10 minutes, high quality)
  - **Gemini Method**: Google's free API (free, high quality)

- **Minutes Generation Model**:
  - **OpenAI Method**: Uses OpenAI's model
  - **Gemini Method**: Uses Google's model

#### Other Settings
- **Seconds for Split Processing**: Unit for splitting long audio for processing (recommended: 300 seconds)
- **Output Directory**: Save location for the minutes

### 📋 Customizing the Content of the Minutes

In the "Specify Minutes Content" tab, you can freely edit the prompts given to the AI. This allows you to specify the content and format you want to include in the minutes.

- **Minutes Generation Prompt**: Instructions to the AI on what kind of minutes to create
- **Reset Button**: Revert to the default prompt

## ⚠️ Notes
- Internet connection is required
- Google's free API key is used for learning, so use a paid API key for company use.
- Speech recognition is not 100% accurate. Please verify the content for important meetings.
- Speaker assignment is particularly incomplete, so please be cautious.

## 🛠️ Customization Using Python

### Direct Editing of Prompt Files
You can directly edit the following files in the `src/prompts/` directory:

- `minutes.txt`: Method and format for creating minutes
- `reflection.txt`: Criteria for meeting reflection analysis
- `transcription.txt`: Rules for formatting transcriptions
- `transcriptionGEMINI.txt`: Rules for formatting transcriptions (GEMINI method)

### Changing AI Models
You can change AI models in the following files in the `src/utils/` directory:

- `Common_OpenAIAPI.py`: Specify OpenAI model (`DEFAULT_CHAT_MODEL = "XXX"`)
- `gemini_api.py`: Specify Gemini model (`model_name="XXX"`) and change maximum character count

## 🔧 Requirements

- Windows 10 or later
- Python 3.9 or later (not required if using the exe file)

## 📦 Required Packages

Please check requirements.txt for details

## 🛠️ Build Method

```bash
pyinstaller GiJiRoKu.spec
```

## 📝 License Information

### AI_GiJiRoKu
MIT License

### FFmpeg
This software uses FFmpeg (https://ffmpeg.org/), which is provided under the following licenses:

- GNU Lesser General Public License (LGPL) version 2.1 or later
- GNU General Public License (GPL) version 2 or later

The source code for FFmpeg is available at:
https://ffmpeg.org/download.html

FFmpeg requires the following copyright notice:
```
This software uses code of FFmpeg (http://ffmpeg.org) licensed under the LGPLv2.1 and its source can be downloaded from https://ffmpeg.org/
```

