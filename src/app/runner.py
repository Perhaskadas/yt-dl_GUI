# src/app/runner.py
from __future__ import annotations

import subprocess
import sys
import threading
import time
import re
import uuid
from dataclasses import dataclass
from typing import Callable, Optional, Dict

DOWNLOAD_PCT_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
DOWNLOAD_DEST_RE = re.compile(r"\[download\] Destination: ")

LogFn = Callable[[str], None]
ProgressFn = Callable[[float], None]  # 0.0 to 100.0
DoneFn = Callable[[int], None]        # exit code (0 = success)
PartFn = Callable[[int], None]        # 1-based index of the file now downloading

# preset -> format selector plus optional merge container / audio conversion
PRESETS: Dict[str, Dict[str, str]] = {
    "best": {"format": "bv*+ba/best"},
    "mp4": {"format": "bv*+ba/best", "merge_output_format": "mp4"},
    "1080p": {"format": "bv*[height<=1080]+ba/best[height<=1080]"},
    "video": {"format": "bv*"},
    "audio": {"format": "ba"},
    "mp3": {"format": "ba", "audio_format": "mp3"},
}
PRESET_ALIASES = {"videoonly": "video", "video_only": "video"}


def _resolve_preset(preset: str, on_log: LogFn) -> Dict[str, str]:
    name = PRESET_ALIASES.get(preset, preset)
    if name not in PRESETS:
        on_log(f"[runner] unknown preset '{preset}', falling back to best")
        name = "best"
    return PRESETS[name]


@dataclass
class JobHandle:
    job_id: str
    stop_event: threading.Event
    proc: subprocess.Popen[str] | None = None


class Runner:
    def __init__(self):
        self._jobs: Dict[str, JobHandle] = {}
        self._lock = threading.Lock()

    def start_ytdlp(
        self,
        url: str,
        out_dir: str,
        preset: str,
        cookies_browser: str,
        on_log: LogFn,
        on_progress: ProgressFn,
        on_part: PartFn,
        on_done: DoneFn,
    ) -> str:
        job_id = uuid.uuid4().hex
        stop_event = threading.Event()
        handle = JobHandle(job_id=job_id, stop_event=stop_event, proc=None)

        with self._lock:
            self._jobs[job_id] = handle

        t = threading.Thread(
            target=self._run_ytdlp,
            args=(handle, url, out_dir, preset, cookies_browser, on_log, on_progress, on_part, on_done),
            daemon=True,
        )
        t.start()
        return job_id

    def stop(self, job_id: str) -> bool:
        with self._lock:
            handle = self._jobs.get(job_id)
        if not handle:
            return False

        handle.stop_event.set()
        proc = handle.proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                # If terminate fails for any reason, try kill as a fallback
                try:
                    proc.kill()
                except Exception:
                    pass

        return True

    def _finish(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def _run_ytdlp(
        self,
        handle: JobHandle,
        url: str,
        out_dir: str,
        preset: str,
        cookies_browser: str,
        on_log: LogFn,
        on_progress: ProgressFn,
        on_part: PartFn,
        on_done: DoneFn,
    ) -> None:
        return_code = 1
        try:
            if _use_inprocess_ytdlp():
                return_code = self._run_ytdlp_inprocess(
                    handle, url, out_dir, preset, cookies_browser, on_log, on_progress, on_part
                )
            else:
                creationflags = 0
                if sys.platform.startswith("win"):
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

                on_log("[runner] starting download")
                on_log(f"[runner] url={url}")
                on_log(f"[runner] out_dir={out_dir}")
                on_log(f"[runner] preset={preset}")
                on_log(f"[runner] cookies={cookies_browser or '(none)'}")

                out_dir = (out_dir or "").strip()
                preset = (preset or "best").strip().lower()
                cookies_browser = (cookies_browser or "").strip().lower()

                # Base command: run yt-dlp from the current venv
                args: list[str] = [sys.executable, "-m", "yt_dlp"]

                # Cookies (optional)
                if cookies_browser:
                    args += ["--cookies-from-browser", cookies_browser]

                # Presets -> yt-dlp flags
                opts = _resolve_preset(preset, on_log)
                args += ["-f", opts["format"]]
                if "merge_output_format" in opts:
                    args += ["--merge-output-format", opts["merge_output_format"]]
                if "audio_format" in opts:
                    args += ["-x", "--audio-format", opts["audio_format"]]

                # Output folder (optional)
                if out_dir:
                    args += ["-P", out_dir]

                # Progress-friendly output; "--" so the URL can never be read as an option
                args += ["--newline", "--", url]

                on_log("[runner] cmd: " + " ".join(args))

                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=creationflags,
                )
                handle.proc = proc

                assert proc.stdout is not None

                part = 0
                for line in proc.stdout:
                    text = line.rstrip("\n")
                    on_log(text)

                    # video+audio presets download one file per stream
                    if DOWNLOAD_DEST_RE.match(text):
                        part += 1
                        on_part(part)

                    m = DOWNLOAD_PCT_RE.search(text)
                    if m:
                        try:
                            on_progress(float(m.group(1)))
                        except ValueError:
                            pass

                    if handle.stop_event.is_set():
                        on_log("[runner] stop requested; terminating yt-dlp...")
                        proc.terminate()
                        break

                proc.stdout.close()
                return_code = proc.wait(timeout=10)

        except subprocess.TimeoutExpired:
            on_log("[runner] terminate timed out; killing yt-dlp...")
            if handle.proc and handle.proc.poll() is None:
                handle.proc.kill()
            return_code = handle.proc.wait() if handle.proc else 1

        except Exception as e:
            on_log(f"[runner] error: {e!r}")
            return_code = 1

        finally:
            handle.proc = None
            on_done(return_code)
            self._finish(handle.job_id)

    def _run_ytdlp_inprocess(
        self,
        handle: JobHandle,
        url: str,
        out_dir: str,
        preset: str,
        cookies_browser: str,
        on_log: LogFn,
        on_progress: ProgressFn,
        on_part: PartFn,
    ) -> int:
        try:
            import yt_dlp

            on_log("[runner] starting download (in-process)")
            on_log(f"[runner] url={url}")
            on_log(f"[runner] out_dir={out_dir}")
            on_log(f"[runner] preset={preset}")
            on_log(f"[runner] cookies={cookies_browser or '(none)'}")

            out_dir = (out_dir or "").strip()
            preset = (preset or "best").strip().lower()
            cookies_browser = (cookies_browser or "").strip().lower()

            opts = _resolve_preset(preset, on_log)
            files_seen: list[str] = []

            def progress_hook(d):
                if handle.stop_event.is_set():
                    raise yt_dlp.utils.DownloadError("Download cancelled")
                if d.get("status") != "downloading":
                    return
                filename = d.get("filename")
                if filename and filename not in files_seen:
                    files_seen.append(filename)
                    on_part(len(files_seen))
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes")
                if total and downloaded is not None:
                    on_progress((downloaded / total) * 100.0)

            ydl_opts: dict = {
                "format": opts["format"],
                "progress_hooks": [progress_hook],
                "logger": _YtDlpLogger(on_log),
            }

            if out_dir:
                ydl_opts["paths"] = {"home": out_dir}

            if cookies_browser:
                ydl_opts["cookiesfrombrowser"] = (cookies_browser,)

            if "merge_output_format" in opts:
                ydl_opts["merge_output_format"] = opts["merge_output_format"]

            if "audio_format" in opts:
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": opts["audio_format"],
                    }
                ]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            return 0
        except Exception as e:
            on_log(f"[runner] error: {e!r}")
            return 1


class _YtDlpLogger:
    def __init__(self, on_log: LogFn):
        self._on_log = on_log

    def debug(self, msg: str):
        if msg:
            self._on_log(str(msg))

    def info(self, msg: str):
        if msg:
            self._on_log(str(msg))

    def warning(self, msg: str):
        if msg:
            self._on_log(f"[warn] {msg}")

    def error(self, msg: str):
        if msg:
            self._on_log(f"[error] {msg}")


def _use_inprocess_ytdlp() -> bool:
    return bool(getattr(sys, "frozen", False))
