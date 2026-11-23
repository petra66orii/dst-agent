"""Offline tests for risk rules, tools, the connector's auth and the agent loop."""
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATA_SOURCE", "local")

from src import agent, repo_data, risk, tools  # noqa: E402


def test_risk_rules():
    ok = risk.check("buy", 3, price=100, stop=90, market_cap=5e9, ideas_this_week=0)
    assert ok.approved and not ok.violations
    bad = risk.check("buy", 20, price=2, stop=2.5, market_cap=50e6, ideas_this_week=9)
    assert not bad.approved and len(bad.violations) == 5
    assert not risk.check("short", 1, 100, 90, 5e9, 0).approved
    assert not risk.check("buy", 3, 100, None, 5e9, 0).approved  # stop required
    assert not risk.check("buy", 3, 100, 70, 5e9, 0).approved   # stop too far
    assert risk.check("sell", 0, 100, None, None, 0).approved     # exits always allowed


def test_tools_never_raise():
    out = tools.get_signal_history("not a ticker!!")
    assert "error" in out


def test_log_idea_blocked_by_risk(monkeypatch):
    monkeypatch.setattr(tools, "check_trade_idea",
                        lambda *a, **k: {"approved": False, "violations": ["x"], "ticker": "ABC"})
    out = tools.log_trade_idea("ABC", "buy", 50, 1, 2, 10, "t", "i", "http://x")
    assert out["logged"] is False


def test_log_idea_writes_row(monkeypatch, tmp_path):
    monkeypatch.setattr(repo_data, "ROOT", tmp_path)
    monkeypatch.setattr(tools, "check_trade_idea", lambda *a, **k: {
        "approved": True, "ticker": "ABC", "price": 100.0, "warnings": [], "violations": []})
    out = tools.log_trade_idea("ABC", "buy", 3, 90, 120, 20, "thesis", "below 90", "https://sec.gov/x", "m")
    assert out["logged"] is True
    text = (tmp_path / "data/agent_ideas.csv").read_text()
    assert text.startswith("logged_at,ticker") and ",ABC,buy,3," in text


def test_tool_schemas():
    specs = {s["name"]: s for s in agent.TOOL_SPECS}
    s = specs["check_trade_idea"]["input_schema"]
    assert s["required"] == ["ticker", "side"] and s["properties"]["position_pct"]["type"] == "number"


class FakeClient:
    """Mimics anthropic.Anthropic: first asks for a tool, then answers."""

    def __init__(self):
        self.calls = 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        if self.calls == 1:
            block = SimpleNamespace(type="tool_use", id="t1", name="get_risk_rules", input={},
                                    model_dump=lambda **_: {"type": "tool_use", "id": "t1",
                                                            "name": "get_risk_rules", "input": {}})
            return SimpleNamespace(stop_reason="tool_use", content=[block])
        assert kw["messages"][-1]["content"][0]["type"] == "tool_result"
        block = SimpleNamespace(type="text", text="Max 5% per position.",
                                model_dump=lambda **_: {"type": "text", "text": "Max 5% per position."})
        return SimpleNamespace(stop_reason="end_turn", content=[block])


def test_agent_loop(monkeypatch):
    monkeypatch.setattr(agent, "ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(agent, "_client", lambda: FakeClient())
    used = []
    reply, history = agent.run([{"role": "user", "content": "rules?"}], on_tool=lambda n, _: used.append(n))
    assert reply == "Max 5% per position." and used == ["get_risk_rules"] and len(history) == 4


def test_trim_history_keeps_tool_pairs():
    msgs = []
    for i in range(20):
        msgs += [{"role": "user", "content": f"q{i}"},
                 {"role": "assistant", "content": [{"type": "tool_use"}]},
                 {"role": "user", "content": [{"type": "tool_result"}]},
                 {"role": "assistant", "content": [{"type": "text"}]}]
    trimmed = agent.trim_history(msgs, max_turns=3)
    assert trimmed[0]["content"] == "q17" and len(trimmed) == 12


@pytest.fixture
def client(monkeypatch):
    from starlette.testclient import TestClient
    from src import mcp_server
    monkeypatch.setattr(mcp_server, "MCP_SECRET", "s3cret")
    with TestClient(mcp_server.build_app()) as c:
        yield c


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "t", "version": "1"}}}
HDRS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def test_connector_auth(client):
    assert client.get("/health").status_code == 200
    assert client.post("/mcp", json=INIT, headers=HDRS).status_code == 401
    assert client.post("/nope/mcp", json=INIT, headers=HDRS).status_code == 401
    assert client.post("/s3cret/mcp", json=INIT, headers=HDRS).status_code == 200
    assert client.post("/mcp", json=INIT, headers={**HDRS, "authorization": "Bearer s3cret"}).status_code == 200
