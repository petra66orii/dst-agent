"""Discord delivery (webhooks) and message formatting."""
from __future__ import annotations

import requests

from src.settings import DISCORD_WEBHOOK_URL

MAX_LEN = 1950


def split_message(content: str, max_length: int = MAX_LEN) -> list[str]:
    chunks, current = [], ""
    for line in content.split("\n"):
        while len(line) > max_length:  # hard-wrap a single oversized line
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:max_length])
            line = line[max_length:]
        if current and len(current) + len(line) + 1 > max_length:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def post(content: str, webhook: str | None = None) -> bool:
    webhook = webhook or DISCORD_WEBHOOK_URL
    if not webhook:
        print("[discord] no webhook set; printing instead\n" + content)
        return False
    for chunk in split_message(content):
        r = requests.post(webhook, json={"content": chunk}, timeout=15)
        if r.status_code not in (200, 204):
            print(f"[discord] {r.status_code}: {r.text[:200]}")
            return False
    return True


def _fmt_component(v: float) -> str:
    return f"{v:+.2f}"


def format_daily(report: dict) -> str:
    lines = [f"📊 **DST Daily — {report['date']}** (benchmark {report.get('benchmark', '')})",
             f"🟢 Buy: {', '.join(report['buy']) or 'None'}",
             f"🔴 Sell: {', '.join(report['sell']) or 'None'}",
             f"🟡 Hold: {', '.join(report['hold']) or 'None'}",
             "", "**Detail** (score = 0.5×trend + 0.25×insider + 0.25×news)"]
    for s in report["signals"]:
        p, c = s.get("price") or {}, s["components"]
        lines.append(
            f"\n🔹 **{s['ticker']}** {s['signal']} ({s['confidence']}) · score {s['score']:+.2f}"
            f"\n• trend {_fmt_component(c['momentum'])} | insider {_fmt_component(c['insider'])} | news {_fmt_component(c['news'])}"
        )
        if p:
            lines.append(f"• ${p['close']:.2f} · 1d {p['ret_1d_pct']:+.1f}% · 20d {p['ret_20d_pct']:+.1f}% "
                         f"({p['rel_20d_pct']:+.1f}% vs bench) · vol {p['vol_annual_pct']}%")
        if s["news"].get("summary"):
            flag = " ⚡catalyst" if s["news"].get("catalyst") else ""
            lines.append(f"• 📰{flag} {s['news']['summary']}")
        for n in (s.get("insiders") or {}).get("notable", [])[:2]:
            lines.append(f"• 🕵️ {n}")
    lines.append("\n_Signals are logged and scored against the benchmark every week. Not advice._")
    return "\n".join(lines)


# Backwards-compatible name used by older scripts
def send_to_discord(report: dict) -> bool:
    return post(format_daily(report))
