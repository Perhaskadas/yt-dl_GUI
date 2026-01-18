# yt-dlp GUI

A lightweight desktop GUI for `yt-dlp`, built with Python and `pywebview`.

This project wraps the `yt-dlp` CLI project in a easy to use GUI.

---

## Features

- Download videos using `yt-dlp` through a desktop GUI
- Live log output streamed from `yt-dlp`
- Start / Stop downloads safely
- Native folder picker
- Runs downloads in a background thread

---

## System Dependencies
- **FFmpeg**
- **Deno**
Missing either of these dependencies will severely limit or prevent the proper running of the interface

---

## Getting Started

### 1) Check dependencies

Windows (PowerShell):
```powershell
ffmpeg -version
deno --version
```

macOS (Terminal):
```bash
ffmpeg -version
deno --version
```

If either command is not found, install it using the steps below.

### 2) Install FFmpeg

Windows (CLI via winget):
```powershell
winget install ffmpeg
```

Windows (manual):
- Download a build from `https://www.ffmpeg.org/download.html`
- Extract the zip and add the `bin` folder to your PATH (if you do not add to PATH, it may not be detected)

macOS (CLI via Homebrew):
```bash
brew install ffmpeg
```

macOS (manual):
- Download a build from `https://www.ffmpeg.org/download.html`
- Move `ffmpeg` to `/usr/local/bin` (or another PATH directory)

### 3) Install Deno

Windows (CLI via winget):
```powershell
winget install Deno
```

Windows (manual):
- Follow the instructions found at https://docs.deno.com/runtime/getting_started/installation/ 

macOS (CLI via Homebrew):
```bash
brew install deno
```

macOS (manual):
- Follow the instructions found at https://docs.deno.com/runtime/getting_started/installation/ 

### 4) Run
Run the downloaded executable file

---

## Packaging (Windows one-file exe)

1. Create and activate your virtual env (optional).
2. Install build tooling:
   - `pip install pyinstaller`
3. Build the exe:
   - `powershell -ExecutionPolicy Bypass -File .\\build.ps1`

The output exe will be in `dist\\yt-dlp-gui.exe` and uses `src\\assets\\yt-dlp-gui.ico` as the Windows icon.
The build collects pywebview runtime files needed for Edge WebView2.
