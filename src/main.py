"""Daily run: analyse watchlist, record signals in the ledger, post to Discord.

    python -m src.main
"""
from src import ledger
from src.dst_agent import analyze_tickers, get_today, load_tickers, save_log
from src.send_report import format_daily, post


def main() -> None:
    result = analyze_tickers(load_tickers())
    report = {"agent": "DST", "date": get_today(), **result}
    save_log(report)
    n = ledger.record(report)
    print(f"Recorded {n} signals in the ledger")
    post(format_daily(report))


if __name__ == "__main__":
    main()
