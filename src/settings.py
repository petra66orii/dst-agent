"""Runtime settings, read from environment variables (or a local .env file).

Nothing here is secret by default; real keys live in .env locally or in
GitHub Actions repository secrets.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv is optional
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"


def _env(name, default=""):
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


# Delivery
DISCORD_WEBHOOK_URL = _env("DISCORD_WEBHOOK_URL")
# Optional separate channel for intraday radar alerts; falls back to the main webhook.
DISCORD_ALERTS_WEBHOOK_URL = _env("DISCORD_ALERTS_WEBHOOK_URL") or DISCORD_WEBHOOK_URL
DISCORD_BOT_TOKEN = _env("DISCORD_BOT_TOKEN")

# LLM for headline sentiment. Anthropic is used if its key is set, else OpenAI, else skipped.
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _env("OPENAI_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-haiku-5-5")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")

# SEC EDGAR requires a descriptive User-Agent with contact details.
SEC_USER_AGENT = _env("SEC_USER_AGENT", "dst-agent research (github.com/petra66orii/dst-agent)")

# Strategy knobs
BENCHMARK = _env("BENCHMARK", "QQQ")
RADAR_MOVE_PCT = float(_env("RADAR_MOVE_PCT", "4"))  # intraday move vs previous close
RADAR_NEWS_SPIKE = int(_env("RADAR_NEWS_SPIKE", "5"))  # headlines in the last 3 hours
