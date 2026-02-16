# src/app/api.py
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webview
import app
from app import deps, updater
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

    # ---------- UI communication ----------

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

    def choose_folder(self):
        assert self._window is not None
        folders = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return folders[0] if folders else None

    def start_download(self, url: str, out_dir: str, preset: str = "best", cookies_browser: str = ""):
        url = (url or "").strip()
        out_dir = (out_dir or "").strip()

        if not url:
            return {"ok": False, "error": "Missing URL"}

        if not out_dir:
            return {"ok": False, "error": "Select an output folder."}

        if self.active_job_id is not None:
            return {"ok": False, "error": "A job is already running"}

        if cookies_browser:
            self._cookies_browser = cookies_browser.lower()

        self._last_out_dir = out_dir
        self._progress_max = 0.0

        job_id = self.runner.start_ytdlp(
            url=url,
            out_dir=out_dir,
            preset=preset,
            cookies_browser=self._resolve_cookies(cookies_browser),
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

    def probe(self, url: str, cookies_browser: str = ""):
        url = (url or "").strip()
        if not url:
            return {"ok": False, "error": "Missing URL"}

        if _use_inprocess_ytdlp():
            return self._probe_inprocess(url, cookies_browser)
        return self._probe_subprocess(url, cookies_browser)

    def set_cookies_browser(self, browser: str):
        self._cookies_browser = (browser or "").strip().lower()
        return {"ok": True}

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

    def system_status(self):
        return {
            "ok": True,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "deno": shutil.which("deno") is not None,
        }

    def install_deps(self):
        def _on_status(text):
            if not self._window:
                return
            payload = json.dumps(text)
            with self._ui_lock:
                self._window.evaluate_js(f"ui.onDepStatus({payload})")

        def _on_progress(dep, pct):
            if not self._window:
                return
            payload = json.dumps({"dep": dep, "pct": pct})
            with self._ui_lock:
                self._window.evaluate_js(f"ui.onDepProgress({payload})")

        def _on_complete(status):
            if not self._window:
                return
            payload = json.dumps(status)
            with self._ui_lock:
                self._window.evaluate_js(f"ui.onDepComplete({payload})")

        t = threading.Thread(
            target=deps.ensure_deps,
            args=(_on_status, _on_progress, _on_complete),
            daemon=True,
        )
        t.start()
        return {"ok": True}

    def check_for_updates(self):
        def _run():
            result = {"app": None, "pip": None}
            try:
                result["app"] = updater.check_for_app_update(app.__version__)
            except Exception:
                pass
            if not getattr(sys, "frozen", False):
                try:
                    result["pip"] = updater.check_pip_updates()
                except Exception:
                    pass
            if not self._window:
                return
            if result["app"] or (result["pip"] and any(result["pip"].values())):
                payload = json.dumps(result)
                with self._ui_lock:
                    self._window.evaluate_js(f"ui.onUpdateAvailable({payload})")

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return {"ok": True}

    def update_pip_deps(self):
        def _run():
            ok = updater.run_pip_update(on_log=self._ui_log)
            if not self._window:
                return
            with self._ui_lock:
                self._window.evaluate_js(f"ui.onPipUpdateComplete({json.dumps(ok)})")

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return {"ok": True}

    # ---------- Private helpers ----------

    def _on_done(self, code: int):
        self._progress_max = 0.0
        self._ui_log(f"[api] job finished with code {code}")
        self.active_job_id = None
        self._ui_done(code)

    def _resolve_cookies(self, cookies_browser: str = "") -> str:
        return (cookies_browser or self._cookies_browser or "").strip().lower()

    def _probe_subprocess(self, url: str, cookies_browser: str = ""):
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        args = [sys.executable, "-m", "yt_dlp"]

        b = self._resolve_cookies(cookies_browser)
        if b:
            args += ["--cookies-from-browser", b]

        args += ["--dump-single-json", "--no-playlist", "--skip-download", url]

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
                creationflags=creationflags,
            )

            out = (proc.stdout or "").strip()

            if proc.returncode != 0:
                last = out.splitlines()[-1] if out else "yt-dlp failed"
                low = out.lower()
                if "cookies" in low or "sign in" in low or "login" in low:
                    last = "Preview needs cookies. Select a browser in Cookies and retry."
                return {"ok": False, "error": last}

            data = _extract_first_json(out)
            if data is None:
                return {"ok": False, "error": "Could not parse preview data. Try switching Cookies, then Refresh."}

            took_ms = int((time.time() - t0) * 1000)
            return {"ok": True, "preview": _build_preview(data, url, took_ms)}

        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Preview timed out"}
        except Exception as e:
            return {"ok": False, "error": repr(e)}

    def _probe_inprocess(self, url: str, cookies_browser: str = ""):
        try:
            import yt_dlp

            ydl_opts: dict = {
                "quiet": True,
                "skip_download": True,
                "noplaylist": True,
                "socket_timeout": 20,
            }

            b = self._resolve_cookies(cookies_browser)
            if b:
                ydl_opts["cookiesfrombrowser"] = (b,)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                data = ydl.extract_info(url, download=False)

            if not data:
                return {"ok": False, "error": "Preview failed"}

            if isinstance(data, dict) and data.get("entries"):
                data = next(iter(data["entries"]), data)

            return {"ok": True, "preview": _build_preview(data, url)}

        except Exception as e:
            return {"ok": False, "error": repr(e)}


# ---------- Module-level helpers ----------

def _build_preview(data: dict, fallback_url: str, took_ms: int = 0) -> dict:
    duration = data.get("duration")
    if not isinstance(duration, int):
        duration = None
    return {
        "title": data.get("title") or "",
        "uploader": data.get("uploader") or data.get("channel") or "",
        "duration": duration,
        "duration_text": _fmt_duration(duration),
        "thumbnail": data.get("thumbnail") or "",
        "webpage_url": data.get("webpage_url") or fallback_url,
        "is_live": bool(data.get("is_live")),
        "extractor": data.get("extractor") or "",
        "took_ms": took_ms,
    }


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


def _use_inprocess_ytdlp() -> bool:
    return bool(getattr(sys, "frozen", False))
