"""Check for app and dependency updates using only stdlib."""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request


def _parse_version(s: str) -> tuple[int, ...]:
    """Strip leading 'v', split on '.', return tuple of ints."""
    return tuple(int(x) for x in s.lstrip("v").split("."))


def check_for_app_update(current_version: str) -> dict | None:
    """Hit GitHub Releases API; return release info dict if newer, else None."""
    url = "https://api.github.com/repos/Perhaskadas/yt-dl_GUI/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    tag = data.get("tag_name", "")
    if not tag:
        return None

    try:
        if _parse_version(tag) <= _parse_version(current_version):
            return None
    except (ValueError, TypeError):
        return None

    return {
        "tag": tag,
        "name": data.get("name") or tag,
        "body": data.get("body") or "",
        "html_url": data.get("html_url") or "",
    }


def check_pip_updates() -> dict[str, str | None]:
    """Return latest pip version for yt-dlp / yt-dlp-ejs if newer than installed.

    Only intended for dev (non-frozen) mode.  Returns e.g.
    {"yt_dlp": "2026.3.1", "yt_dlp_ejs": None}
    """
    result: dict[str, str | None] = {"yt_dlp": None, "yt_dlp_ejs": None}
    for pkg, key in [("yt-dlp", "yt_dlp"), ("yt-dlp-ejs", "yt_dlp_ejs")]:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "index", "versions", pkg],
                capture_output=True, text=True, timeout=10,
            )
            if proc.returncode != 0:
                continue
            # Output like: "yt-dlp (2026.03.01)"
            out = proc.stdout.strip()
            latest = out.split("(")[1].split(")")[0].strip() if "(" in out else None
            if not latest:
                continue
            # Compare to installed
            installed = subprocess.run(
                [sys.executable, "-m", "pip", "show", pkg],
                capture_output=True, text=True, timeout=10,
            )
            for line in installed.stdout.splitlines():
                if line.startswith("Version:"):
                    cur = line.split(":", 1)[1].strip()
                    if _parse_version(latest) > _parse_version(cur):
                        result[key] = latest
                    break
        except Exception:
            continue
    return result


def run_pip_update(on_log) -> bool:
    """Run pip install -U yt-dlp yt-dlp-ejs, streaming output to callback."""
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp", "yt-dlp-ejs"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        for line in proc.stdout:
            if on_log:
                on_log(line.rstrip("\n"))
        proc.wait(timeout=120)
        return proc.returncode == 0
    except Exception as e:
        if on_log:
            on_log(f"[updater] error: {e}")
        return False
