import sys
from app.runner import RUN_YTDLP_FLAG

# The packaged app has no separate Python, so downloads run by re-launching
# this executable as "<app> --run-yt-dlp <yt-dlp args>" (see runner.ytdlp_command).
# Handle that before importing the GUI so the child never loads pywebview.
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == RUN_YTDLP_FLAG:
    import yt_dlp
    yt_dlp.main(sys.argv[2:])  # exits via SystemExit with yt-dlp's return code

from pathlib import Path
import inspect
import os
import webview
from app.api import Api
from app.deps import get_bin_dir

def main():
    bin_dir = get_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")

    # The static ffmpeg builds ship their own OpenSSL with no CA store, so
    # ffmpeg can't verify HTTPS (clip downloads, some HLS streams) unless it
    # is pointed at a bundle. Leave any user-provided setting alone.
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parents[1]
    ui_dir = base_dir / "ui"
    assets_dir = base_dir / "assets"
    icon_path = None

    if sys.platform.startswith("darwin"):
        candidate = assets_dir / "yt-dlp-gui.icns"
        if candidate.exists():
            icon_path = str(candidate)
    elif sys.platform.startswith("win"):
        for name in ("yt-dlp-gui-taskbar.ico", "yt-dlp-gui.ico"):
            candidate = assets_dir / name
            if candidate.exists():
                icon_path = str(candidate)
                break
    else:
        candidate = assets_dir / "yt-dlp-gui.ico"
        if candidate.exists():
            icon_path = str(candidate)

    api = Api()

    window_kwargs = {
        "title": "YouTube Downloader",
        "url": str(ui_dir / "index.html"),   # load local file
        "js_api": api,
        "width": 1040,
        "height": 720,
        "min_size": (520, 600),
    }
    if icon_path and "icon" in inspect.signature(webview.create_window).parameters:
        window_kwargs["icon"] = icon_path

    window = webview.create_window(**window_kwargs)

    def on_ready():
        # Attach after pywebview finishes JS API introspection to weird recursion limit bug
        print(f"pywebview renderer: {webview.renderer}.")
        api.attach_window(window)

    start_kwargs = {}
    if icon_path and "icon" in inspect.signature(webview.start).parameters:
        start_kwargs["icon"] = icon_path
    webview.start(on_ready, **start_kwargs)

if __name__ == "__main__":
    main()
