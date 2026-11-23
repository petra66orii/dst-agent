#!/usr/bin/env bash
# Start the Discord bot from the repo root (reads keys from .env)
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.discord_bot
