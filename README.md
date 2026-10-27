# yt-dlp GUI

A lightweight desktop GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp), built with Python and [pywebview](https://pywebview.flowrl.com/).

Download videos and audio from YouTube and hundreds of other sites through a clean, native desktop interface

---

## Features

- **Video or audio** — Best quality up to 4K or capped at 1440p/1080p/720p/480p/360p, video-only, or audio as Original, MP3, M4A, Opus, FLAC or WAV with a choice of bitrate
- **File type choice** — Automatic, MP4, MP4 with H.264 (plays everywhere, up to 1080p), WebM or MKV
- **Playlists** — Links to a video inside a playlist download just that video by default, or the whole playlist into its own folder, with a list of every video's title and duration
- **Clips** — Download only part of a video; links with a timestamp (`&t=90s`) fill in the start time
- **Subtitles** — Embed English subtitles, optionally including auto-generated ones
- **Cover art, metadata and chapters** — Embedded into the file with one checkbox
- **Live preview** — Paste a link to see the title, channel, duration and thumbnail before downloading
- **Real-time progress** — Progress bar (per video in a playlist) and live log output from yt-dlp
- **Reliable cancel** — Stop ends yt-dlp and ffmpeg immediately and removes partial files
- **Browser cookies** — Use your signed-in session from any installed browser (Chrome, Firefox, Safari, Edge, Brave, Vivaldi and more) for age-restricted or members-only videos
- **Auto-install dependencies** — FFmpeg, FFprobe and Deno are downloaded on first launch if missing (pinned versions, verified by SHA-256)
- **Auto-update notifications** — Checks GitHub releases on startup and tells you when a new version is available
- **Native look** — Light and dark appearance following the system, a two-pane layout on wide windows, and Cmd/Ctrl +/− text scaling
- **Cross-platform** — macOS and Windows

---

## Getting Started

### Download and run

Download the latest release from the [Releases page](https://github.com/Perhaskadas/yt-dl_GUI/releases):

- **macOS** — Unzip `yt-dlp-gui-macos.zip` and drag `yt-dlp-gui.app` into Applications.
- **Windows** — Unzip `yt-dlp-gui-windows.zip` and run `yt-dlp-gui.exe` inside the `yt-dlp-gui` folder. Keep the `_internal` folder next to it; the app needs it.

FFmpeg, FFprobe and Deno are installed automatically on first launch if they aren't already on your system.

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

- **FFmpeg** — Required for merging video/audio streams, audio conversion and clips
- **FFprobe** — Comes with FFmpeg; used when embedding cover art and converting audio
- **Deno** — Required by yt-dlp-ejs for extracting certain sites

All three are auto-installed to a local app directory on first launch if not found on your PATH (macOS and Windows only; pinned versions, verified by SHA-256). On other platforms, install them with your package manager. You can also install them manually:

| | macOS (Homebrew) | Windows (winget) |
|---|---|---|
| FFmpeg + FFprobe | `brew install ffmpeg` | `winget install ffmpeg` |
| Deno | `brew install deno` | `winget install Deno` |

---

## Packaging (Windows)

1. Create and activate a virtual env (optional).
2. Install build tooling:
   ```
   pip install pyinstaller
   ```
3. Build the exe:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\build.ps1
   ```

The app is built as a folder, `dist\yt-dlp-gui\`, containing `yt-dlp-gui.exe` and an `_internal` folder; ship the whole folder. It uses `src\assets\yt-dlp-gui.ico` as the Windows icon.
It's a one-dir build rather than a single exe because a one-file exe unpacks itself on every launch, and the app launches itself again for each download.
The build collects pywebview runtime files needed for Edge WebView2.
