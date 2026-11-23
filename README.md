# 📈 DST Trading Agent

Watches a list of US stocks, gives each a Buy / Hold / Sell signal every day, **records every signal and checks whether it actually beat the market**, and sends intraday alerts when something material happens (8-K filings, big moves, news spikes). Everything is delivered to Discord.

Everything runs for free on GitHub Actions. No paid data APIs.

## How it works

| Job | When (UTC, Mon–Fri) | What it does |
|---|---|---|
| **Daily signals** (`src/main.py`) | 22:15, after the US close | Scores each watchlist ticker, posts the report, appends to `data/signals.csv` |
| **Event radar** (`src/radar.py`) | hourly 14:05–21:05 | New 8-K filings (🚨 for high-impact items like 5.02 exec changes, 2.02 earnings), moves ≥4% vs previous close, news spikes |
| **Weekly scorecard** (`src/scorecard.py`) | Fri 22:45 | 1/5/20-day returns of every past signal vs the benchmark (QQQ): hit rate, average excess return, Buy−Sell spread, and which inputs are predictive |

### Signal = 0.5 × trend + 0.25 × insider + 0.25 × news

- **Trend** (`market_data.py`): 20-day performance relative to QQQ plus whether price is above its 50/200-day averages. Ignores the 1-day move on purpose.
- **Insider** (`edgar.py`, SEC EDGAR Form 4): only **open-market purchases** by officers/directors count, and several insiders buying at once (cluster buying) scores highest. Stock grants, option exercises, tax withholdings and pre-planned 10b5-1 sales are ignored.
- **News** (`llm.py` + Google News RSS): an LLM scores headlines from −1 to +1 and is told to stay near 0 unless there's a concrete company-specific event.

Score ≥ 0.25 → Buy, ≤ −0.25 → Sell (±0.5 = high confidence).

### The rule that matters

The weights above are a starting guess. **Use the scorecard to decide what to trust.** Wait until there are 100+ signals over 3+ months, and only think about real money if Buy signals beat QQQ at 20 days after costs. If one input's correlation stays at or below 0, cut its weight.

## Setup

### GitHub Actions (recommended)

Add these under **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Required | Notes |
|---|---|---|
| `SEC_USER_AGENT` | ✅ | e.g. `Petra dst-agent you@example.com`. SEC requires contact details |
| `DISCORD_WEBHOOK_URL` | ✅ | Channel for daily reports and scorecard |
| `DISCORD_ALERTS_WEBHOOK_URL` | optional | Separate channel for radar alerts |
| `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | optional | Without one, news scores 0 |

Then **Actions → Daily signals → Run workflow** to test. Each job also has a manual "Run workflow" button.

### Local

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in values
python -m src.main       # daily signals
python -m src.radar      # one radar sweep
python -m src.scorecard  # scorecard
python -m src.discord_bot  # interactive bot: type a ticker, or $analyze NVDA
python -m pytest -q      # offline tests
```

Watchlist: `data/stocks.json`. Benchmark and radar thresholds: see `.env.example`.

## Files

```
src/
  main.py         daily run
  dst_agent.py    scoring engine
  market_data.py  yfinance prices + trend features
  edgar.py        SEC EDGAR: CIK lookup, Form 4 parsing, 8-K items
  llm.py          headline sentiment (Anthropic / OpenAI)
  news_scraper.py Google News RSS
  ledger.py       data/signals.csv
  scorecard.py    forward-return evaluation
  radar.py        intraday alerts
  send_report.py  Discord formatting/delivery
  discord_bot.py  interactive bot
tests/            offline unit tests
```

## Next steps

- Backtest the trend and insider components on several years of data (news can't be backtested reliably)
- Paper-trade the Buy list via Alpaca's paper API once the scorecard shows an edge
- Position sizing by volatility; stop rules

---

**Disclaimer**: Educational/research tool. Not financial advice.
