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

    api.attach_window(window)
    webview.start(debug=True)

if __name__ == "__main__":
    main()