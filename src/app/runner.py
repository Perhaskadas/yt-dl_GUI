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

LogFn = Callable[[str], None]
ProgressFn = Callable[[float], None]  # 0.0 to 100.0
DoneFn = Callable[[int], None]        # exit code (0 = success)


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
        on_log: LogFn,
        on_progress: ProgressFn,
        on_done: DoneFn,
    ) -> str:
        job_id = uuid.uuid4().hex
        stop_event = threading.Event()
        handle = JobHandle(job_id=job_id, stop_event=stop_event, proc=None)

        with self._lock:
            self._jobs[job_id] = handle

        t = threading.Thread(
            target=self._run_ytdlp,
            args=(handle, url, out_dir, on_log, on_progress, on_done),
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
        on_log: LogFn,
        on_progress: ProgressFn,
        on_done: DoneFn,
    ) -> None:
        return_code = 1
        try:
            on_log(f"[runner] starting download")
            on_log(f"[runner] url={url}")
            on_log(f"[runner] out_dir={out_dir}")
            
            out_dir = (out_dir or "").strip()
            if not out_dir:
                args = [
                    sys.executable, "-m", "yt_dlp",
                    "--cookies-from-browser", "firefox",
                    url,
                    "-f", "bv*+ba/best",
                    "--newline",
                ]
            else:
                args = [sys.executable, "-m", "yt_dlp", 
                        url,
                        "-P", out_dir,
                        "-f", "bv*+ba/best",
                        "--newline"]
            on_log("[runner] cmd: " + " ".join(args))

            # Run the yt-dlp command in a subprocess
            proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
            # Store the Popen so that we can read from it later
            handle.proc = proc   

            assert proc.stdout is not None   

            for line in proc.stdout:
                # log stdout
                text = line.rstrip("\n")
                on_log(text)

                # Try to parse the percentage out of the logs
                m = DOWNLOAD_PCT_RE.search(text)
                if m:
                    try:
                        pct = float(m.group(1))
                        on_progress(pct)
                    except ValueError:
                        pass

                # handle stop command
                if handle.stop_event.is_set():
                    on_log("[runner] stop requested; terminating yt-dlp...")
                    proc.terminate()
                    break
            if proc.stdout:
                proc.stdout.close()

            return_code = proc.wait(timeout=10)

        except subprocess.TimeoutExpired:
            # If terminate didn't work, kill it
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
