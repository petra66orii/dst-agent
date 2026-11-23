"""Offline tests: no network, synthetic data only."""
import numpy as np
import pandas as pd
import pytest

from src import dst_agent, edgar, ledger, market_data, radar, scorecard
from src.send_report import format_daily, split_message

FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>0</isDirector><isOfficer>true</isOfficer>
      <officerTitle>Chief Executive Officer</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <aff10b5One>0</aff10b5One>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-11-20</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>150.5</value><footnoteId id="F1"/></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-11-20</value></transactionDate>
      <transactionCoding><transactionCode>F</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>300</value></transactionShares>
        <transactionPricePerShare><value>150</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


def test_parse_form4_and_ignore_non_market_codes():
    txns = edgar.parse_form4(FORM4)
    assert [t["code"] for t in txns] == ["P", "F"]
    assert txns[0]["value"] == pytest.approx(150500)
    s = edgar.summarise_insiders("XYZ", txns)
    assert s["buyers"] == 1 and s["sellers"] == 0  # tax withholding (F) is ignored
    assert edgar.score_insiders(s) == pytest.approx(0.4)


def test_cluster_buying_scores_highest_and_10b5_1_sales_ignored():
    base = {"is_officer": True, "is_director": False, "title": "", "date": "", "shares": 1, "price": 1, "value": 1}
    buys = [dict(base, insider=f"I{i}", code="P", plan_10b5_1=False) for i in range(3)]
    planned = [dict(base, insider=f"S{i}", code="S", plan_10b5_1=True) for i in range(5)]
    assert edgar.score_insiders(edgar.summarise_insiders("X", buys + planned)) == 1.0
    assert edgar.summarise_insiders("X", planned)["sellers"] == 0


def test_parse_submissions_filters_form_and_date():
    data = {"filings": {"recent": {
        "form": ["8-K", "4", "8-K"],
        "filingDate": ["2026-11-23", "2026-11-23", "2026-10-01"],
        "acceptanceDateTime": ["", "", ""],
        "accessionNumber": ["0001-26-1", "0001-26-2", "0001-26-3"],
        "primaryDocument": ["a.htm", "xslF345X05/f4.xml", "b.htm"],
        "items": ["5.02,9.01", "", "2.02"],
    }}}
    out = edgar.parse_submissions(data, {"8-K"}, pd.Timestamp("2026-11-20").date())
    assert len(out) == 1 and out[0]["items"] == ["5.02", "9.01"]


def _prices(n=260, drift=0.001, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2025-11-01", periods=n)
    return pd.Series(100 * np.exp(np.cumsum(drift + rng.normal(0, 0.003, n))), index=idx)


def test_momentum_positive_for_outperformer_negative_for_laggard():
    bench = _prices(drift=0.0, seed=1)
    up = market_data.score_momentum(market_data.price_features(_prices(drift=0.004, seed=2), bench))
    down = market_data.score_momentum(market_data.price_features(_prices(drift=-0.004, seed=3), bench))
    assert up > 0.5 and down < -0.5


def test_classify_thresholds():
    assert dst_agent.classify(0.6) == ("Buy", "High")
    assert dst_agent.classify(0.3) == ("Buy", "Low")
    assert dst_agent.classify(0.0) == ("Hold", "Neutral")
    assert dst_agent.classify(-0.3) == ("Sell", "Low")


def _report(date="2026-11-20"):
    return {"date": date, "benchmark": "QQQ", "benchmark_close": 500.0, "buy": ["AAA"], "sell": ["BBB"], "hold": [],
            "signals": [
                {"ticker": "AAA", "signal": "Buy", "confidence": "High", "score": 0.6,
                 "components": {"momentum": 1, "insider": 0.4, "news": 0.2},
                 "price": {"close": 100, "ret_1d_pct": 1, "ret_20d_pct": 5, "rel_20d_pct": 3,
                           "above_ma50": True, "above_ma200": True, "vol_annual_pct": 30},
                 "news": {"summary": "ok", "sentiment_score": 0.2, "catalyst": False},
                 "insiders": {"notable": ["X BUY 1 @ $1"]}},
                {"ticker": "BBB", "signal": "Sell", "confidence": "Low", "score": -0.3,
                 "components": {"momentum": -0.6, "insider": 0, "news": 0},
                 "price": {"close": 50, "ret_1d_pct": -1, "ret_20d_pct": -5, "rel_20d_pct": -7,
                           "above_ma50": False, "above_ma200": False, "vol_annual_pct": 40},
                 "news": {"summary": "", "sentiment_score": 0, "catalyst": False}, "insiders": {}},
            ]}


def test_ledger_is_idempotent_per_day(tmp_path):
    path = tmp_path / "signals.csv"
    assert ledger.record(_report(), path) == 2
    ledger.record(_report(), path)  # same day re-run replaces, not duplicates
    ledger.record(_report("2026-11-21"), path)
    rows = ledger.read(path)
    assert len(rows) == 4 and {r["date"] for r in rows} == {"2026-11-20", "2026-11-21"}


def test_scorecard_forward_returns_and_summary(tmp_path):
    idx = pd.bdate_range("2026-11-16", periods=30)
    closes = pd.DataFrame({
        "AAA": np.linspace(100, 130, 30),  # rises 30%
        "BBB": np.linspace(50, 40, 30),    # falls
        "QQQ": np.full(30, 500.0),         # flat benchmark
    }, index=idx)
    path = tmp_path / "s.csv"
    ledger.record(_report(), path)
    df = scorecard.forward_returns(ledger.read(path), closes)
    aaa = df[df.ticker == "AAA"].iloc[0]
    pos = idx.get_loc(pd.Timestamp("2026-11-20"))
    assert aaa["ret_5d"] == pytest.approx(closes.AAA.iloc[pos + 5] / closes.AAA.iloc[pos] - 1)
    assert aaa["excess_5d"] == pytest.approx(aaa["ret_5d"])  # flat benchmark
    summ = scorecard.summarise(df)
    assert summ["by_signal"]["Buy"][5]["hit_rate"] == 1.0
    assert summ["by_signal"]["Sell"][5]["hit_rate"] == 1.0  # BBB lagged: Sell was right
    assert summ["spread"][5] > 0
    text = scorecard.format_scorecard(summ, 2, "2026-11-20")
    assert "Only 2 signals" in text


def test_weekend_signal_maps_to_previous_trading_day():
    idx = pd.bdate_range("2026-11-16", periods=10)
    closes = pd.DataFrame({"AAA": range(10), "QQQ": [1.0] * 10}, index=idx, dtype=float) + 1
    rows = [{"date": "2026-11-22", "ticker": "AAA", "signal": "Buy", "score": 1, "momentum": 1,
             "insider": 0, "news": 0, "benchmark": "QQQ"}]  # a Sunday
    df = scorecard.forward_returns(rows, closes)
    assert df.iloc[0]["ret_1d"] == pytest.approx(6 / 5 - 1)  # Fri close 5 -> Mon close 6


def test_radar_move_buckets_and_filing_dedupe(monkeypatch):
    assert radar.move_bucket(3.9, 4) == 0 and radar.move_bucket(-8.5, 4) == 2
    monkeypatch.setattr(edgar, "recent_filings", lambda cik, forms, since: [
        {"form": "8-K", "filed": "2026-11-23", "accession": "0001045810-26-000090",
         "primary_doc": "nov23.htm", "items": ["5.02", "9.01"]}])
    state = {"seen_filings": [], "alerted": []}
    first = radar.check_filings("NVDA", 1045810, state, None)
    assert len(first) == 1 and "5.02 Executive/director change" in first[0] and first[0].startswith("🚨")
    assert radar.check_filings("NVDA", 1045810, state, None) == []


def test_discord_split_and_format():
    chunks = split_message("x" * 5000 + "\nshort")
    assert all(len(c) <= 1950 for c in chunks) and chunks[-1].endswith("short")
    assert "AAA" in format_daily(_report())
