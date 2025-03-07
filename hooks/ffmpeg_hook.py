import sys, os
from pathlib import Path

if hasattr(sys, '_MEIPASS'):
    ffmpeg_path = Path(sys._MEIPASS) / "resources" / "ffmpeg" / "ffmpeg.exe"
else:
    ffmpeg_path = Path("resources") / "ffmpeg" / "ffmpeg.exe"

if ffmpeg_path.exists():
    os.environ["FFMPEG_BINARY"] = str(ffmpeg_path)
else:
    import shutil
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        os.environ["FFMPEG_BINARY"] = system_ffmpeg