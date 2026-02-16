# yt-dlp GUI

A lightweight desktop GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp), built with Python and [pywebview](https://pywebview.flowrl.com/).

Download videos and audio from YouTube and hundreds of other sites through a clean, native desktop interface

---

## Features

- **6 download presets** — Best quality, MP4, 1080p, video-only, audio-only, MP3
- **Live video preview** — Paste a URL to see title, uploader, duration, and thumbnail before downloading
- **Real-time progress** — Progress bar and live log output streamed from yt-dlp
- **Browser cookie support** — Use cookies from Firefox, Chrome, or Safari for age-gated or login-required content
- **Auto-install dependencies** — FFmpeg and Deno are downloaded automatically on first launch if missing
- **Auto-update notifications** — Checks GitHub releases on startup and notifies you when a new version is available
- **Dark / Light theme** — Toggle between themes, or auto-detect from system preference
- **Start / Stop downloads** — Cancel running downloads safely
- **Native folder picker** — Choose output directory with the OS file dialog
- **Cross-platform** — macOS and Windows

---

## Getting Started

### Download and run

Download the latest release from the [Releases page](https://github.com/Perhaskadas/yt-dl_GUI/releases) and run the executable. FFmpeg and Deno will be installed automatically on first launch if they aren't already on your system.

### Run from source

Requires Python 3.10+.

```bash
git clone https://github.com/Perhaskadas/yt-dl_GUI.git
cd yt-dl_GUI
pip install -e .
python -m app.main
```

---

## System Dependencies

- **FFmpeg** — Required for merging video/audio streams and MP3 conversion
- **Deno** — Required by yt-dlp-ejs for extracting certain sites

Both are auto-installed to a local app directory on first launch if not found on your PATH. You can also install them manually:

| | macOS (Homebrew) | Windows (winget) |
|---|---|---|
| FFmpeg | `brew install ffmpeg` | `winget install ffmpeg` |
| Deno | `brew install deno` | `winget install Deno` |

---

## Packaging (Windows one-file exe)

1. Create and activate a virtual env (optional).
2. Install build tooling:
   ```
   pip install pyinstaller
   ```
3. Build the exe:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\build.ps1
   ```

The output exe will be in `dist\yt-dlp-gui.exe` and uses `src\assets\yt-dlp-gui.ico` as the Windows icon.
The build collects pywebview runtime files needed for Edge WebView2.
