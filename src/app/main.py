from pathlib import Path
import webview
from app.api import Api

def main():
    ui_dir = Path(__file__).resolve().parents[1] / "ui"
    api = Api()

    window = webview.create_window(
        title="yt-dlp GUI",
        url=str(ui_dir / "index.html"),   # load local file
        js_api=api,
        width=1000,
        height=700,
    )

    def on_ready():
        # Attach after pywebview finishes JS API introspection to avoid recursion
        print(f"pywebview renderer: {webview.renderer}.")
        api.attach_window(window)

    webview.start(on_ready)

if __name__ == "__main__":
    main()
