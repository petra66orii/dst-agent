"""Read (and optionally append to) files in the GitHub repo.

The daily GitHub Action commits logs/ and data/signals.csv, so the repo is the single
source of truth. The always-on server (connector + Discord agent) reads them from GitHub
rather than its own disk, which is wiped on every restart.

Set DATA_SOURCE=local to read from the working copy instead (local dev, tests).
"""
from __future__ import annotations

import base64
import os
import time

import requests

from src.settings import ROOT

GITHUB_REPO = os.getenv("GITHUB_REPO", "petra66orii/dst-agent")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "master")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()  # needed for private repo or for logging ideas
DATA_SOURCE = os.getenv("DATA_SOURCE", "github")

_API = "https://api.github.com/repos/{repo}/contents/{path}"
_cache: dict[str, tuple[float, object]] = {}
CACHE_SECONDS = 300


def _headers(raw: bool = False) -> dict:
    h = {"Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "dst-agent"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _cached(key: str, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    value = fn()
    _cache[key] = (time.time(), value)
    return value


def read_text(path: str) -> str | None:
    if DATA_SOURCE == "local":
        p = ROOT / path
        return p.read_text() if p.exists() else None

    def fetch():
        r = requests.get(_API.format(repo=GITHUB_REPO, path=path), params={"ref": GITHUB_BRANCH},
                         headers=_headers(raw=True), timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text

    return _cached(f"file:{path}", fetch)


def list_dir(path: str) -> list[str]:
    if DATA_SOURCE == "local":
        p = ROOT / path
        return sorted(x.name for x in p.iterdir()) if p.exists() else []

    def fetch():
        r = requests.get(_API.format(repo=GITHUB_REPO, path=path), params={"ref": GITHUB_BRANCH},
                         headers=_headers(), timeout=20)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return sorted(item["name"] for item in r.json())

    return _cached(f"dir:{path}", fetch)


def append_line(path: str, line: str, header: str, message: str) -> bool:
    """Append a line to a text file (creating it with `header`). Needs GITHUB_TOKEN with
    contents:write on this repo. Returns False if logging isn't configured."""
    if DATA_SOURCE == "local":
        p = ROOT / path
        p.parent.mkdir(exist_ok=True)
        new = not p.exists()
        with open(p, "a") as f:
            f.write((header + "\n" if new else "") + line + "\n")
        return True
    if not GITHUB_TOKEN:
        return False
    url = _API.format(repo=GITHUB_REPO, path=path)
    for _ in range(3):  # retry on concurrent-write conflicts
        r = requests.get(url, params={"ref": GITHUB_BRANCH}, headers=_headers(), timeout=20)
        if r.status_code == 404:
            sha, current = None, header + "\n"
        else:
            r.raise_for_status()
            body = r.json()
            sha, current = body["sha"], base64.b64decode(body["content"]).decode()
        if not current.endswith("\n"):
            current += "\n"
        payload = {"message": message, "branch": GITHUB_BRANCH,
                   "content": base64.b64encode((current + line + "\n").encode()).decode()}
        if sha:
            payload["sha"] = sha
        put = requests.put(url, json=payload, headers=_headers(), timeout=20)
        if put.status_code in (200, 201):
            _cache.pop(f"file:{path}", None)
            return True
        if put.status_code != 409:
            put.raise_for_status()
    return False
