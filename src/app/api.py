# src/app/api.py
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse
import webview
from app.runner import Runner


class Api:
    def __init__(self):
        self._window = None
        self.runner = Runner()
        self.active_job_id: str | None = None
        self._ui_lock = threading.Lock()
        self._progress_max = 0.0
        self._last_out_dir = ""
        self._cookies_browser: str = ""

    def attach_window(self, window):
        self._window = window

    def choose_folder(self):
        assert self._window is not None
        folders = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return folders[0] if folders else None


    # ---------- helpers to safely talk to UI ----------
    def _ui_log(self, line: str):
        if not self._window:
            return
        payload = json.dumps(line)
        with self._ui_lock:
            self._window.evaluate_js(f"ui.onLog({payload})")

    def _ui_progress(self, pct: float):
        if not self._window:
            return

        pct = max(0.0, min(100.0, pct))

        if pct >= 99.9 and self._progress_max < 95.0:
            return
    
        if pct < self._progress_max:
            pct = self._progress_max
        else:
            self._progress_max = pct

        with self._ui_lock:
            self._window.evaluate_js(f"ui.onProgress({pct})")

    def _ui_done(self, code: int):
        if not self._window:
            return
        
        out_dir_json = json.dumps(self._last_out_dir)
        with self._ui_lock:
            self._window.evaluate_js(f"ui.onJobEnd({code}, {out_dir_json})")

    # ---------- JS-callable methods ----------
    def start_download(self, url: str, out_dir: str, preset: str = "best", cookies_browser: str = ""):
        url = (url or "").strip()
        out_dir = (out_dir or "").strip()

        if not url:
            return {"ok": False, "error": "Missing URL"}
        
        if not out_dir:
            return {"ok":False, "error": "Select an output folder."}

        if self.active_job_id is not None:
            return {"ok": False, "error": "A job is already running"}
        
        if cookies_browser:
            self._cookies_browser = cookies_browser.lower()
        
        # Start runner
        self._last_out_dir = out_dir
        self._progress_max = 0.0

        job_id = self.runner.start_ytdlp(
            url=url,
            out_dir=out_dir,
            preset=preset,
            cookies_browser=(cookies_browser or self._cookies_browser),
            on_log=self._ui_log,
            on_progress=self._ui_progress,
            on_done=self._on_done,
        )
        self.active_job_id = job_id
        self._ui_log(f"[api] started job {job_id}")
        return {"ok": True, "job_id": job_id}

    def stop(self):
        if not self.active_job_id:
            return {"ok": False, "error": "No active job"}

        ok = self.runner.stop(self.active_job_id)
        return {"ok": ok}

    def _on_done(self, code: int):
        # Called from runner thread
        self._progress_max = 0.0
        self._ui_log(f"[api] job finished with code {code}")
        self.active_job_id = None
        self._ui_done(code)

    def open_folder(self, path: str):
        path = (path or "").strip()
        if not path:
            return {"ok": False, "error": "No folder path provided"}

        if not os.path.isdir(path):
            return {"ok": False, "error": f"Folder does not exist: {path}"}

        try:
            if sys.platform.startswith("darwin"):
                subprocess.run(["open", path], check=False)
            elif sys.platform.startswith("win32"):
                subprocess.run(["explorer", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": repr(e)}
        
    def probe(self, url: str, cookies_browser: str = ""):
        url = (url or "").strip()
        if not url:
            return {"ok": False, "error": "Missing URL"}

        args = [sys.executable, "-m", "yt_dlp"]

        b = (cookies_browser or self._cookies_browser or "").strip().lower()
        if b:
            args += ["--cookies-from-browser", b]

        args += [
            "--dump-single-json",
            "--no-playlist",
            "--skip-download",
            url,
        ]

        try:
            t0 = time.time()
            proc = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )

            out = (proc.stdout or "").strip()

            if proc.returncode != 0:
                # show last line as a short error, but also hint cookies
                last = out.splitlines()[-1] if out else "yt-dlp failed"
                low = out.lower()
                if "cookies" in low or "sign in" in low or "login" in low:
                    last = "Preview needs cookies. Select a browser in Cookies and retry."
                return {"ok": False, "error": last}

            data = _extract_first_json(out)
            if data is None:
                msg = "Could not parse preview data. Try switching Cookies, then Refresh."
                return {"ok": False, "error": msg}

            duration = data.get("duration")
            preview = {
                "title": data.get("title") or "",
                "uploader": data.get("uploader") or data.get("channel") or "",
                "duration": duration if isinstance(duration, int) else None,
                "duration_text": _fmt_duration(duration if isinstance(duration, int) else None),
                "thumbnail": data.get("thumbnail") or "",
                "webpage_url": data.get("webpage_url") or url,
                "is_live": bool(data.get("is_live")),
                "extractor": data.get("extractor") or "",
                "took_ms": int((time.time() - t0) * 1000),
            }
            return {"ok": True, "preview": preview}

        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Preview timed out"}
        except Exception as e:
            return {"ok": False, "error": repr(e)}
        
    def set_cookies_browser(self, browser: str):
        self._cookies_browser = (browser or "").strip().lower()
        return {"ok": True}
    
    def _ytdlp_base_args(self, cookies_browser: str | None = None) -> list[str]:
        b = (cookies_browser or self._cookies_browser or "").strip().lower()
        args = [sys.executable, "-m", "yt_dlp"]  # IMPORTANT: yt_dlp module name
        if b:
            args += ["--cookies-from-browser", b]
        return args




def _fmt_duration(seconds: int | None) -> str:
    if not seconds or seconds < 0:
        return ""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def _extract_first_json(text: str) -> dict | None:
    if not text:
        return None

    i = text.find("{")
    if i == -1:
        return None

    try:
        obj, _ = json.JSONDecoder().raw_decode(text[i:])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None
