"""Headline sentiment via an LLM (Anthropic preferred, OpenAI fallback, else neutral)."""
from __future__ import annotations

import json
import re

import requests

from src.settings import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, OPENAI_API_KEY, OPENAI_MODEL

NEUTRAL = {"summary": "", "sentiment_score": 0.0, "catalyst": False}

PROMPT = """You are an equity analyst. Judge the likely near-term (1-4 week) price impact of these
headlines for {ticker}. Most headlines are noise: if nothing is new and material, score near 0.
Only score beyond +/-0.5 for concrete, company-specific events (earnings surprise, guidance change,
leadership change, major contract, regulatory action, M&A).

Headlines:
{headlines}

Reply with JSON only:
{{"summary": "<2 sentences>", "sentiment_score": <float -1..1>, "catalyst": <true if a material company-specific event>}}"""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON in reply")
    data = json.loads(match.group(0))
    data["sentiment_score"] = max(min(float(data.get("sentiment_score", 0)), 1.0), -1.0)
    data["catalyst"] = bool(data.get("catalyst", False))
    data["summary"] = str(data.get("summary", ""))[:400]
    return data


def analyse_headlines(ticker: str, headlines: list[str]) -> dict:
    if not headlines:
        return dict(NEUTRAL, summary="No recent headlines.")
    prompt = PROMPT.format(ticker=ticker, headlines="\n".join(f"- {h}" for h in headlines))
    try:
        if ANTHROPIC_API_KEY:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": ANTHROPIC_MODEL, "max_tokens": 300,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60,
            )
            r.raise_for_status()
            return _extract_json(r.json()["content"][0]["text"])
        if OPENAI_API_KEY:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model": OPENAI_MODEL, "temperature": 0.2,
                      "response_format": {"type": "json_object"},
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60,
            )
            r.raise_for_status()
            return _extract_json(r.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"[llm] {ticker}: {e}")
        return dict(NEUTRAL, summary="LLM analysis failed; neutral score used.")
    return dict(NEUTRAL, summary="No LLM key set; news not scored.")
