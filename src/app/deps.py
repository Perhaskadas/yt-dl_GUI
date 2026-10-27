# src/app/deps.py
"""Auto-download portable ffmpeg, ffprobe and deno binaries on first launch."""
from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import sys
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Binary sources (pinned versions, verified by SHA-256)
# ---------------------------------------------------------------------------

_DENO_RELEASE = "https://github.com/denoland/deno/releases/download/v2.9.8"
_FFMPEG_MACOS = "https://ffmpeg.martin-riedl.de/download/macos"
_FFMPEG_WIN = "https://github.com/GyanD/codexffmpeg/releases/download/9.0.2"

# Binaries the app needs on PATH (ffprobe is used by yt-dlp's embed/convert steps)
REQUIRED_BINARIES = ("ffmpeg", "ffprobe", "deno")


class Package(NamedTuple):
    name: str                 # shown in the setup sheet ("downloading_<name>")
    url: str
    sha256: str               # of the zip
    binaries: tuple[str, ...]  # executables to extract (without .exe)


_PACKAGES: dict[str, list[Package]] = {
    "darwin_arm64": [
        Package(
            "ffmpeg",
            f"{_FFMPEG_MACOS}/arm64/1789931890_9.0.2/ffmpeg.zip",
            "c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924",
            ("ffmpeg",),
        ),
        Package(
            "ffprobe",
            f"{_FFMPEG_MACOS}/arm64/1789931890_9.0.2/ffprobe.zip",
            "fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6",
            ("ffprobe",),
        ),
        Package(
            "deno",
            f"{_DENO_RELEASE}/deno-aarch64-apple-darwin.zip",
            "9f0bf660393da2eaff044cdc7444cb08c73f235849b61d224d825a194ce7c98e",
            ("deno",),
        ),
    ],
    "darwin_x86_64": [
        Package(
            "ffmpeg",
            f"{_FFMPEG_MACOS}/amd64/1789931006_9.0.2/ffmpeg.zip",
            "7c6b4125b191cbf773832dc51f424cf2b6bb7da43007d1e066f95909e47cacd4",
            ("ffmpeg",),
        ),
        Package(
            "ffprobe",
            f"{_FFMPEG_MACOS}/amd64/1789931006_9.0.2/ffprobe.zip",
            "2322438ed2f6319a691291b247d09c69dcaa3a982460d1f269a7e1af335cfdfd",
            ("ffprobe",),
        ),
        Package(
            "deno",
            f"{_DENO_RELEASE}/deno-x86_64-apple-darwin.zip",
            "4b2f5edd2639b7470f034238b321d7002d8dfb4726d8558f52c17afac370eb2c",
            ("deno",),
        ),
    ],
    "win32_x86_64": [
        # One zip carries both ffmpeg.exe and ffprobe.exe
        Package(
            "ffmpeg",
            f"{_FFMPEG_WIN}/ffmpeg-9.0.2-essentials_build.zip",
            "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba",
            ("ffmpeg", "ffprobe"),
        ),
        Package(
            "deno",
            f"{_DENO_RELEASE}/deno-x86_64-pc-windows-msvc.zip",
            "cba84b26e0df5ae7f74fc66b86a95b866872a86292ebd84fa1e959927edd93bf",
            ("deno",),
        ),
    ],
}

# Windows on ARM runs the x64 builds under emulation
_PACKAGES["win32_arm64"] = _PACKAGES["win32_x86_64"]


def _platform_key() -> str:
    if sys.platform.startswith("win"):
        plat = "win32"
    elif sys.platform == "darwin":
        plat = "darwin"
    else:
        plat = sys.platform
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
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "yt-dlp-gui" / "bin"


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def check_deps() -> dict[str, bool]:
    return {name: shutil.which(name) is not None for name in REQUIRED_BINARIES}


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


def _exe(name: str) -> str:
    return f"{name}.exe" if sys.platform.startswith("win") else name


def _install_package(package: Package, bin_dir: Path, on_progress):
    data = _download_with_progress(package.url, on_progress)
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != package.sha256:
        raise RuntimeError(f"{package.name} checksum mismatch (got {actual_sha256})")

    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        for binary in package.binaries:
            exe_name = _exe(binary)
            # The binary may be nested in a bin/ folder inside the zip
            target = next((n for n in names if n.rsplit("/", 1)[-1] == exe_name), None)
            if target is None:
                raise RuntimeError(f"{exe_name} not found inside {package.name} zip")

            # Extract to bin_dir with flat name; write to a temp file first so a
            # failed extraction never leaves a truncated binary on PATH
            dest = bin_dir / exe_name
            tmp = dest.with_name(dest.name + ".part")
            with zf.open(target) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            _make_executable(tmp)
            os.replace(tmp, dest)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def ensure_deps(on_status, on_progress, on_complete):
    """Check and install missing deps. Callbacks are called from the caller's thread.

    on_status(text)          — e.g. "downloading_ffmpeg"
    on_progress(dep, pct)    — 0-100 or -1 on failure
    on_complete(result)      — {"ffmpeg": bool, "ffprobe": bool, "deno": bool}
    """
    status = check_deps()
    missing = {name for name, present in status.items() if not present}
    if not missing:
        on_complete(status)
        return

    key = _platform_key()
    packages = [p for p in _PACKAGES.get(key, []) if missing & set(p.binaries)]
    if not packages:
        print(f"[deps] no bundled binaries for {key}; install {', '.join(sorted(missing))} manually")
        on_complete(status)
        return

    bin_dir = get_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)

    for package in packages:
        on_status(f"downloading_{package.name}")
        try:
            def _progress(read, total, _dep=package.name):
                pct = (read / total * 100) if total > 0 else -1
                on_progress(_dep, pct)

            _install_package(package, bin_dir, _progress)
            for binary in package.binaries:
                status[binary] = True
        except Exception as exc:
            print(f"[deps] failed to install {package.name}: {exc}")
            on_progress(package.name, -1)

    on_complete(status)
