# src/app/runner.py
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from glob import escape as glob_escape
from pathlib import Path
from typing import Callable, Dict

DOWNLOAD_PCT_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
DOWNLOAD_DEST_RE = re.compile(r"\[download\] Destination: ")
PLAYLIST_ITEM_RE = re.compile(r"\[download\] Downloading item (\d+) of (\d+)")
SECTION_TIME_RE = re.compile(r"^\d+(?::\d{1,2}){0,2}(?:\.\d+)?$")
# File paths in yt-dlp's log: 'Destination: <path>', '... to: <path>', or '"<path>"'
FILE_PATH_RE = re.compile(r'(?:Destination|to): (.+)$|"([^"]+)"')

# Argument that makes the packaged app run yt-dlp instead of the GUI (main.py)
RUN_YTDLP_FLAG = "--run-yt-dlp"

LogFn = Callable[[str], None]
ProgressFn = Callable[[float], None]  # 0.0 to 100.0
DoneFn = Callable[[int, bool], None]  # exit code (0 = success), cancelled by the user
PartFn = Callable[[int], None]        # 1-based index of the file now downloading
ItemFn = Callable[[int, int], None]   # playlist item index, total

KINDS = ("video", "audio", "video_only")
CONTAINERS = ("auto", "mp4", "mp4_h264", "webm", "mkv")

# container -> extra args. Format sorting (-S) picks streams that fit the
# container natively instead of forcing e.g. VP9/Opus into an MP4.
CONTAINER_ARGS: dict[str, list[str]] = {
    "auto": [],
    # Highest resolution first (AV1 above 1080p on YouTube), then MP4/M4A streams
    "mp4": ["-S", "res,ext:mp4:m4a", "--merge-output-format", "mp4", "--remux-video", "mp4"],
    # H.264 + AAC beats resolution: plays everywhere, 1080p max on YouTube
    "mp4_h264": ["-S", "vcodec:h264,res,acodec:aac", "--merge-output-format", "mp4", "--remux-video", "mp4"],
    # WebM can't hold everything (e.g. cover art), so yt-dlp may fall back to MKV
    "webm": ["-S", "res,ext:webm:webm", "--merge-output-format", "webm/mkv"],
    "mkv": ["--merge-output-format", "mkv", "--remux-video", "mkv"],
}
AUDIO_FORMATS = ("best", "mp3", "m4a", "opus", "flac", "wav")
LOSSY_AUDIO = ("mp3", "m4a", "opus")
AUDIO_QUALITIES = ("0", "320K", "256K", "192K", "128K")  # "0" = best VBR
SUBTITLE_MODES = ("off", "en", "en_auto")
SUBTITLE_LANGS = "en,en-US,en-GB"  # exact codes: "en.*" also matches dozens of auto-translations
PLAYLIST_TEMPLATE = "%(playlist_title|Playlist)s/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"


@dataclass
class DownloadOptions:
    kind: str = "video"
    max_height: int = 0           # 0 = no cap
    container: str = "auto"
    audio_format: str = "best"
    audio_quality: str = "0"
    subtitles: str = "off"
    embed_extras: bool = False    # cover art, metadata, chapters
    section_start: str = ""       # [[h:]m:]s, "" = from the beginning
    section_end: str = ""         # "" = to the end
    playlist: bool = False
    cookies_browser: str = ""
    concurrent_fragments: int = 1

    @classmethod
    def from_dict(cls, data: dict | None) -> "DownloadOptions":
        """Build from untrusted UI input, falling back to defaults on anything unexpected."""
        data = data or {}
        d = cls()

        def pick(key, allowed, default):
            value = str(data.get(key, default)).strip()
            return value if value in allowed else default

        d.kind = pick("kind", KINDS, d.kind)
        d.container = pick("container", CONTAINERS, d.container)
        d.audio_format = pick("audio_format", AUDIO_FORMATS, d.audio_format)
        d.audio_quality = pick("audio_quality", AUDIO_QUALITIES, d.audio_quality)
        d.subtitles = pick("subtitles", SUBTITLE_MODES, d.subtitles)
        d.embed_extras = bool(data.get("embed_extras"))
        d.playlist = bool(data.get("playlist"))
        d.cookies_browser = str(data.get("cookies_browser") or "").strip().lower()

        try:
            d.max_height = max(0, min(4320, int(data.get("max_height") or 0)))
        except (TypeError, ValueError):
            d.max_height = 0
        try:
            d.concurrent_fragments = max(1, min(16, int(data.get("concurrent_fragments") or 1)))
        except (TypeError, ValueError):
            d.concurrent_fragments = 1

        for key in ("section_start", "section_end"):
            value = str(data.get(key) or "").strip()
            if value and not SECTION_TIME_RE.match(value):
                raise ValueError(f"Invalid time '{value}'. Use seconds, m:ss or h:mm:ss.")
            setattr(d, key, value)

        return d


def build_args(url: str, out_dir: str, opts: DownloadOptions) -> list[str]:
    """yt-dlp command-line arguments for a download (without the program name).

    Both run modes use these: the subprocess passes them to yt-dlp directly,
    the in-process path converts them with yt_dlp.parse_options().
    """
    args: list[str] = []

    if opts.cookies_browser:
        args += ["--cookies-from-browser", opts.cookies_browser]

    # Format selection
    h = opts.max_height
    if opts.kind == "audio":
        args += ["-f", "ba/b", "-x", "--audio-format", opts.audio_format]
        if opts.audio_format in LOSSY_AUDIO:
            args += ["--audio-quality", opts.audio_quality]
    elif opts.kind == "video_only":
        args += ["-f", f"bv*[height<={h}]/bv*" if h else "bv*"]
    else:
        # Fall back to the best available if nothing fits under the cap
        args += ["-f", f"bv*[height<={h}]+ba/b[height<={h}]/bv*+ba/b" if h else "bv*+ba/b"]

    if opts.kind != "audio":
        if opts.embed_extras and opts.container in ("auto", "webm"):
            # WebM can't hold cover art: merge into MP4 when the streams allow it
            # (Automatic) or MKV, and remux single-file WebM downloads to MKV
            sort = CONTAINER_ARGS[opts.container][:2]  # keep the -S preference, if any
            merge = "mkv" if opts.container == "webm" else "mp4/mkv"
            args += [*sort, "--merge-output-format", merge, "--remux-video", "webm>mkv"]
        else:
            args += CONTAINER_ARGS[opts.container]
        if opts.subtitles != "off":
            args += ["--embed-subs", "--sub-langs", SUBTITLE_LANGS]
            if opts.subtitles == "en_auto":
                args += ["--write-auto-subs"]

    if opts.embed_extras:
        args += ["--embed-metadata", "--embed-chapters"]
        # WAV has no cover art support
        if not (opts.kind == "audio" and opts.audio_format == "wav"):
            args += ["--embed-thumbnail"]

    if opts.section_start or opts.section_end:
        args += ["--download-sections", f"*{opts.section_start or '0'}-{opts.section_end or 'inf'}"]

    if opts.playlist:
        args += ["--yes-playlist", "-o", PLAYLIST_TEMPLATE]
    else:
        args += ["--no-playlist"]

    # Parallel fragment downloads (only affects DASH/HLS formats)
    if opts.concurrent_fragments > 1:
        args += ["-N", str(opts.concurrent_fragments)]

    if out_dir:
        args += ["-P", out_dir]

    # Progress-friendly output; "--" so the URL can never be read as an option
    args += ["--newline", "--", url]
    return args


class _LineWatcher:
    """Turns yt-dlp's log lines into part/playlist-item events, and remembers
    which files the current item has touched so a cancel can clean them up."""

    def __init__(self, on_part: PartFn, on_item: ItemFn, out_dir: str):
        self._on_part = on_part
        self._on_item = on_item
        self._out_dir = Path(out_dir).resolve() if out_dir else None
        self._part = 0
        self.current_files: set[Path] = set()

    def feed(self, text: str) -> None:
        m = PLAYLIST_ITEM_RE.search(text)
        if m:
            # The previous playlist item finished: its files are kept
            self._part = 0
            self.current_files.clear()
            self._on_item(int(m.group(1)), int(m.group(2)))
            return
        # video+audio formats download one file per stream
        if DOWNLOAD_DEST_RE.match(text):
            self._part += 1
            self._on_part(self._part)
        self._track_paths(text)

    def _track_paths(self, text: str) -> None:
        if self._out_dir is None:
            return
        for raw in FILE_PATH_RE.findall(text):
            path = next(p for p in raw if p).strip()
            try:
                resolved = (self._out_dir / path).resolve()
            except (OSError, ValueError):
                continue
            # Only ever track files inside the chosen download folder
            if resolved.is_relative_to(self._out_dir):
                self.current_files.add(resolved)


def _cleanup_partial(files: set[Path], started_at: float, on_log: LogFn) -> None:
    """Delete what a cancelled item left behind: partial downloads, unmerged
    streams, half-converted files. Files older than the job are never touched."""
    candidates: set[Path] = set()
    for f in files:
        candidates |= {f, f.with_name(f.name + ".part"), f.with_name(f.name + ".ytdl"),
                       f.with_name(f"{f.stem}.temp{f.suffix}")}
        candidates |= set(f.parent.glob(glob_escape(f.name) + ".part-Frag*"))

    removed = 0
    for c in candidates:
        try:
            if c.is_file() and c.stat().st_mtime >= started_at - 2:
                c.unlink()
                removed += 1
        except OSError as e:
            on_log(f"[runner] couldn't remove {c.name}: {e}")
    if removed:
        on_log(f"[runner] removed {removed} partial file(s)")


def ytdlp_command() -> list[str]:
    """How to start yt-dlp as a child process. The packaged app re-launches
    itself in yt-dlp mode (see main.py) since there is no separate Python."""
    if getattr(sys, "frozen", False):
        return [sys.executable, RUN_YTDLP_FLAG]
    return [sys.executable, "-m", "yt_dlp"]


def _popen_group_kwargs() -> dict:
    # Own process group, so Stop can take down yt-dlp *and* the ffmpeg it starts
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return {"creationflags": flags}
    return {"start_new_session": True}


def _kill_tree(proc: subprocess.Popen, force: bool = False) -> None:
    if proc.poll() is not None:
        return
    if sys.platform.startswith("win"):
        # /T includes child processes (ffmpeg); /F because console signals
        # don't reach a windowless process group
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            pass


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
        opts: DownloadOptions,
        on_log: LogFn,
        on_progress: ProgressFn,
        on_part: PartFn,
        on_item: ItemFn,
        on_done: DoneFn,
    ) -> str:
        job_id = uuid.uuid4().hex
        stop_event = threading.Event()
        handle = JobHandle(job_id=job_id, stop_event=stop_event, proc=None)

        with self._lock:
            self._jobs[job_id] = handle

        t = threading.Thread(
            target=self._run_ytdlp,
            args=(handle, url, out_dir, opts, on_log, on_progress, on_part, on_item, on_done),
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
        if proc is not None:
            try:
                _kill_tree(proc)
            except Exception:
                # If the polite stop fails for any reason, force it
                try:
                    _kill_tree(proc, force=True)
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
        opts: DownloadOptions,
        on_log: LogFn,
        on_progress: ProgressFn,
        on_part: PartFn,
        on_item: ItemFn,
        on_done: DoneFn,
    ) -> None:
        return_code = 1
        out_dir = (out_dir or "").strip()
        watcher = _LineWatcher(on_part, on_item, out_dir)
        started_at = time.time()
        try:
            cmd = [*ytdlp_command(), *build_args(url, out_dir, opts)]
            on_log("[runner] starting download")
            on_log("[runner] cmd: " + " ".join(cmd))

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                # The packaged app's child must write UTF-8 to the pipe too
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
                **_popen_group_kwargs(),
            )
            handle.proc = proc
            if handle.stop_event.is_set():
                # Stop was pressed while the process was starting
                _kill_tree(proc)

            assert proc.stdout is not None

            for line in proc.stdout:
                text = line.rstrip("\n")
                on_log(text)
                watcher.feed(text)

                m = DOWNLOAD_PCT_RE.search(text)
                if m:
                    try:
                        on_progress(float(m.group(1)))
                    except ValueError:
                        pass

            proc.stdout.close()
            return_code = proc.wait(timeout=10)

        except subprocess.TimeoutExpired:
            on_log("[runner] yt-dlp didn't exit; killing it...")
            if handle.proc:
                _kill_tree(handle.proc, force=True)
                return_code = handle.proc.wait()

        except Exception as e:
            on_log(f"[runner] error: {e!r}")
            return_code = 1

        finally:
            cancelled = handle.stop_event.is_set()
            if cancelled:
                on_log("[runner] download cancelled")
                _cleanup_partial(watcher.current_files, started_at, on_log)
            handle.proc = None
            on_done(return_code, cancelled)
            self._finish(handle.job_id)
