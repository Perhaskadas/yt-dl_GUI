from pathlib import Path
import inspect
import os
import sys
import webview
from app.api import Api
from app.deps import get_bin_dir

def main():
    bin_dir = get_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")

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
        "title": "yt-dlp GUI",
        "url": str(ui_dir / "index.html"),   # load local file
        "js_api": api,
        "width": 1000,
        "height": 700,
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
