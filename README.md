# yt-dlp GUI

A lightweight desktop GUI for `yt-dlp`, built with Python and `pywebview`.

This project wraps the powerful `yt-dlp` CLI in a simple, responsive graphical interface while preserving full functionality and performance.

---

## Features

- Download videos using `yt-dlp` through a desktop GUI
- Live log output streamed from `yt-dlp`
- Start / Stop downloads safely
- Native folder picker
- Runs downloads in a background thread (UI never freezes)

---

## Final Plan
Be runnable as a self contained and easy to download .exe file

## System Dependencies
- **FFmpeg** (currently required for most formats and audio/video merging, may be bundled into .exe file later)

---

## Packaging (Windows one-file exe)

1. Create and activate your virtual env (optional).
2. Install build tooling:
   - `pip install pyinstaller`
3. Build the exe:
   - `powershell -ExecutionPolicy Bypass -File .\\build.ps1`

The output exe will be in `dist\\yt-dlp-gui.exe` and uses `src\\assets\\yt-dlp-gui.ico` as the Windows icon.
