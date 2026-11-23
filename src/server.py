"""Always-on service: MCP connector (HTTP) + Discord agent, in one process.

    python -m src.server

PORT is set by Render; defaults to 8000 locally. The Discord bot starts only if
DISCORD_BOT_TOKEN is set, so the same code can run as connector-only.
"""
import asyncio
import os

import uvicorn

from src.mcp_server import build_app
from src.settings import DISCORD_BOT_TOKEN


async def main():
    config = uvicorn.Config(build_app(), host="0.0.0.0", port=int(os.getenv("PORT", "8000")),
                            log_level="info", proxy_headers=True, forwarded_allow_ips="*")
    web = uvicorn.Server(config)
    jobs = [web.serve()]
    if DISCORD_BOT_TOKEN:
        from src.discord_bot import bot
        jobs.append(bot.start(DISCORD_BOT_TOKEN))
    else:
        print("DISCORD_BOT_TOKEN not set: running connector only")
    await asyncio.gather(*jobs)


if __name__ == "__main__":
    asyncio.run(main())
