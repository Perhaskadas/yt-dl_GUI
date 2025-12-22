# src/app/api.py
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import webview
from app.runner import Runner


class Api:
    def __init__(self):
        self.window = None
        self.runner = Runner()
        self.active_job_id: str | None = None
        self._ui_lock = threading.Lock()
        self._progress_max = 0.0
        self._last_out_dir = ""

    def attach_window(self, window):
        self.window = window

    def choose_folder(self):
        assert self.window is not None
        folders = self.window.create_file_dialog(webview.FileDialog.FOLDER)
        return folders[0] if folders else None


    # ---------- helpers to safely talk to UI ----------
    def _ui_log(self, line: str):
        if not self.window:
            return
        payload = json.dumps(line)
        with self._ui_lock:
            self.window.evaluate_js(f"ui.onLog({payload})")

    def _ui_progress(self, pct: float):
        if not self.window:
            return

        pct = max(0.0, min(100.0, pct))

        if pct >= 99.9 and self._progress_max < 95.0:
            return
    
        if pct < self._progress_max:
            pct = self._progress_max
        else:
            self._progress_max = pct

        with self._ui_lock:
            self.window.evaluate_js(f"ui.onProgress({pct})")

    def _ui_done(self, code: int):
        if not self.window:
            return
        
        out_dir_json = json.dumps(self._last_out_dir)
        with self._ui_lock:
            self.window.evaluate_js(f"ui.onJobEnd({code}, {out_dir_json})")

    # ---------- JS-callable methods ----------
    def start_download(self, url: str, out_dir: str):
        url = (url or "").strip()
        out_dir = (out_dir or "").strip()

        if not url:
            return {"ok": False, "error": "Missing URL"}

        if self.active_job_id is not None:
            return {"ok": False, "error": "A job is already running"}
        
        self._last_out_dir = out_dir

        # Start runner
        self.progress_max = 0.0
        job_id = self.runner.start_ytdlp(
            url=url,
            out_dir=out_dir,
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
