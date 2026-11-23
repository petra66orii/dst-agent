"""MCP connector exposing the DST tools, so Claude (claude.ai custom connector) and any
MCP-capable agent can use them.

Authentication: a shared secret (MCP_SECRET). Clients can send it either as
`Authorization: Bearer <secret>` or in the URL path: https://<host>/<secret>/mcp
(the path form is for clients like claude.ai custom connectors that take just a URL).
"""
from __future__ import annotations

import hmac
import os

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from src import tools
from src.risk import rules_text

MCP_SECRET = os.getenv("MCP_SECRET", "").strip()

INSTRUCTIONS = f"""DST tools for US-stock research. Data comes from SEC EDGAR, yfinance, Google News
(tagged verified/unverified) and the DST bot's own signal ledger and scorecard.
Rules: cite filing/news URLs for factual claims; treat unverified headlines as rumour; check the
scorecard before trusting any signal; ideas must pass check_trade_idea. Hard risk rules: {rules_text()}
Logging an idea never places an order."""

server = MCPServer(name="dst-agent", instructions=INSTRUCTIONS, version="1.0.0")

for fn in tools.ALL_TOOLS:
    read_only = fn.__name__ in tools.READ_ONLY
    server.add_tool(fn, annotations=ToolAnnotations(read_only_hint=read_only, destructive_hint=False,
                                                     open_world_hint=True))


@server.custom_route("/health", methods=["GET"])
async def health(_: Request):
    return JSONResponse({"ok": True})


def build_app():
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        # Auth is enforced by the middleware below; the host check would reject the public hostname.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        host="0.0.0.0",
    )
    return SecretAuth(app, MCP_SECRET)


class SecretAuth:
    """ASGI middleware: allow /health, otherwise require the secret (path prefix or bearer)."""

    def __init__(self, app, secret: str):
        self.app, self.secret = app, secret

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == "/health":
            return await self.app(scope, receive, send)
        if not self.secret:
            return await self._deny(send, 503, "MCP_SECRET not configured")
        path = scope["path"]
        prefix = f"/{self.secret}"
        if path.startswith(prefix + "/") and hmac.compare_digest(path[: len(prefix)], prefix):
            scope = dict(scope, path=path[len(prefix):], raw_path=path[len(prefix):].encode())
            return await self.app(scope, receive, send)
        auth = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
        if auth.startswith("Bearer ") and hmac.compare_digest(auth[7:].strip(), self.secret):
            return await self.app(scope, receive, send)
        return await self._deny(send, 401, "unauthorised")

    @staticmethod
    async def _deny(send, status, msg):
        await JSONResponse({"error": msg}, status_code=status)(
            {"type": "http"}, None, send)  # type: ignore[arg-type]
