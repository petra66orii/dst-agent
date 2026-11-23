"""Append-only record of every signal, so performance can be measured later."""
from __future__ import annotations

import csv
from pathlib import Path

from src.settings import DATA_DIR

LEDGER = DATA_DIR / "signals.csv"
FIELDS = ["date", "ticker", "signal", "confidence", "score",
          "momentum", "insider", "news", "entry_close", "benchmark", "benchmark_close"]


def record(report: dict, path: Path = LEDGER) -> int:
    """Write one row per ticker for the report's date. Re-running the same day replaces that day."""
    rows = read(path)
    rows = [r for r in rows if r["date"] != report["date"]]
    added = 0
    for s in report["signals"]:
        close = (s.get("price") or {}).get("close")
        if close is None:
            continue  # no price, nothing to measure against
        rows.append({
            "date": report["date"],
            "ticker": s["ticker"],
            "signal": s["signal"],
            "confidence": s["confidence"],
            "score": s["score"],
            "momentum": s["components"]["momentum"],
            "insider": s["components"]["insider"],
            "news": s["components"]["news"],
            "entry_close": close,
            "benchmark": report.get("benchmark", ""),
            "benchmark_close": report.get("benchmark_close", ""),
        })
        added += 1
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["date"], r["ticker"])))
    return added


def read(path: Path = LEDGER) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))
