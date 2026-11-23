"""Price data via yfinance (free, no API key)."""
from __future__ import annotations

import pandas as pd


def _yf():
    import yfinance as yf  # imported lazily so tests and imports work offline

    return yf


def get_closes(tickers: list[str], period: str = "1y", start: str | None = None) -> pd.DataFrame:
    """Daily adjusted closes, one column per ticker, indexed by date."""
    tickers = sorted(set(tickers))
    kwargs = {"start": start} if start else {"period": period}
    raw = _yf().download(tickers, auto_adjust=True, progress=False, threads=True, **kwargs)
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        closes = raw["Close"]
    else:  # older yfinance, single ticker
        closes = raw[["Close"]].rename(columns={"Close": tickers[0]})
    closes.index = pd.to_datetime(closes.index).tz_localize(None).normalize()
    return closes.dropna(how="all")


def get_intraday(ticker: str) -> pd.DataFrame:
    """Last two sessions of 5-minute bars (used by the radar)."""
    df = _yf().Ticker(ticker).history(period="2d", interval="5m", auto_adjust=True)
    return df if df is not None else pd.DataFrame()


def price_features(series: pd.Series, bench: pd.Series) -> dict:
    """Trend/momentum features for one ticker from daily closes."""
    s = series.dropna()
    b = bench.reindex(s.index).ffill()
    if len(s) < 60:
        return {}
    last = float(s.iloc[-1])
    ret_1d = last / float(s.iloc[-2]) - 1
    ret_20d = last / float(s.iloc[-21]) - 1
    bench_20d = float(b.iloc[-1]) / float(b.iloc[-21]) - 1
    ma50 = float(s.iloc[-50:].mean())
    ma200 = float(s.iloc[-200:].mean()) if len(s) >= 200 else None
    vol_20d = float(s.pct_change().iloc[-20:].std() * (252 ** 0.5))
    return {
        "close": round(last, 4),
        "ret_1d_pct": round(ret_1d * 100, 2),
        "ret_20d_pct": round(ret_20d * 100, 2),
        "rel_20d_pct": round((ret_20d - bench_20d) * 100, 2),
        "above_ma50": last > ma50,
        "above_ma200": None if ma200 is None else last > ma200,
        "vol_annual_pct": round(vol_20d * 100, 1),
    }


def score_momentum(f: dict) -> float:
    """-1..1. Trend-following: relative strength vs benchmark plus moving-average regime.

    Deliberately ignores the 1-day move (chasing yesterday's jump is noise).
    """
    if not f:
        return 0.0
    rel = max(min(f["rel_20d_pct"] / 10, 1), -1)  # +/-10% vs benchmark saturates
    regime = (0.5 if f["above_ma50"] else -0.5)
    if f.get("above_ma200") is not None:
        regime += 0.5 if f["above_ma200"] else -0.5
    else:
        regime *= 2
    return round(0.6 * rel + 0.4 * regime, 3)
