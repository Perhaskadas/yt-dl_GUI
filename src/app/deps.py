# src/app/deps.py
"""Auto-download portable ffmpeg and deno binaries on first launch."""
from __future__ import annotations

import os
import platform
import shutil
import stat
import sys
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

# ---------------------------------------------------------------------------
# Binary source URLs
# ---------------------------------------------------------------------------

_DENO_URLS: dict[str, str] = {
    "darwin_arm64": "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-apple-darwin.zip",
    "darwin_x86_64": "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-apple-darwin.zip",
    "win32_x86_64": "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip",
}

_FFMPEG_URLS: dict[str, str] = {
    "darwin_arm64": "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/snapshot/ffmpeg.zip",
    "darwin_x86_64": "https://ffmpeg.martin-riedl.de/redirect/latest/macos/amd64/snapshot/ffmpeg.zip",
    "win32_x86_64": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
}


def _platform_key() -> str:
    plat = "win32" if sys.platform.startswith("win") else "darwin"
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        arch = "x86_64"
    return f"{plat}_{arch}"


# ---------------------------------------------------------------------------
# App data directory
# ---------------------------------------------------------------------------

def get_bin_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / "Library" / "Application Support"
    return base / "yt-dlp-gui" / "bin"


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def check_deps() -> dict[str, bool]:
    return {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "deno": shutil.which("deno") is not None,
    }


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _download_with_progress(url: str, on_progress) -> bytes:
    """Download *url* into memory, calling on_progress(bytes_read, total)."""
    req = urllib.request.Request(url, headers={"User-Agent": "yt-dlp-gui/1.0"})
    resp = urllib.request.urlopen(req, timeout=120)
    total = int(resp.headers.get("Content-Length", 0))
    buf = BytesIO()
    read = 0
    while True:
        chunk = resp.read(64 * 1024)
        if not chunk:
            break
        buf.write(chunk)
        read += len(chunk)
        if on_progress:
            on_progress(read, total)
    return buf.getvalue()


def _make_executable(path: Path):
    if not sys.platform.startswith("win"):
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _install_deno(bin_dir: Path, on_progress):
    key = _platform_key()
    url = _DENO_URLS.get(key)
    if not url:
        raise RuntimeError(f"No deno binary available for {key}")

    data = _download_with_progress(url, on_progress)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        exe_name = "deno.exe" if sys.platform.startswith("win") else "deno"
        zf.extract(exe_name, bin_dir)
    _make_executable(bin_dir / exe_name)


def _install_ffmpeg(bin_dir: Path, on_progress):
    key = _platform_key()
    url = _FFMPEG_URLS.get(key)
    if not url:
        raise RuntimeError(f"No ffmpeg binary available for {key}")

    data = _download_with_progress(url, on_progress)
    exe_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"

    with zipfile.ZipFile(BytesIO(data)) as zf:
        # Find the ffmpeg binary inside the zip (may be nested in a bin/ folder)
        target = None
        for name in zf.namelist():
            basename = name.rsplit("/", 1)[-1] if "/" in name else name
            if basename == exe_name:
                target = name
                break
        if target is None:
            raise RuntimeError(f"{exe_name} not found inside zip")

        # Extract to bin_dir with flat name
        dest = bin_dir / exe_name
        with zf.open(target) as src, open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)

    _make_executable(bin_dir / exe_name)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def ensure_deps(on_status, on_progress, on_complete):
    """Check and install missing deps. Callbacks are called from the caller's thread.

    on_status(text)          — e.g. "downloading_ffmpeg"
    on_progress(dep, pct)    — 0-100 or -1 on failure
    on_complete(result)      — {"ffmpeg": bool, "deno": bool}
    """
    status = check_deps()
    to_install: list[tuple[str, callable]] = []

    if not status["ffmpeg"]:
        to_install.append(("ffmpeg", _install_ffmpeg))
    if not status["deno"]:
        to_install.append(("deno", _install_deno))

    if not to_install:
        on_complete(status)
        return

    bin_dir = get_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)

    for dep_name, installer in to_install:
        on_status(f"downloading_{dep_name}")
        try:
            def _progress(read, total, _dep=dep_name):
                pct = (read / total * 100) if total > 0 else -1
                on_progress(_dep, pct)

            installer(bin_dir, _progress)
            status[dep_name] = True
        except Exception as exc:
            print(f"[deps] failed to install {dep_name}: {exc}")
            on_progress(dep_name, -1)
            status[dep_name] = False

    on_complete(status)
