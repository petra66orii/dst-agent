"""SEC EDGAR client (free, no API key). Used for insider trades (Form 4) and 8-K events.

SEC fair-access rules: <=10 requests/second and a User-Agent with contact details.
"""
from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import requests

from src.settings import DATA_DIR, SEC_USER_AGENT

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"

_CIK_CACHE = DATA_DIR / "cik_map.json"
_last_call = 0.0

# 8-K item codes worth knowing about. 5.02 = officer/director departure or appointment
# (the NVIDIA CEO reinstatement was filed under this item).
EIGHT_K_ITEMS = {
    "1.01": "Material agreement",
    "1.02": "Agreement terminated",
    "1.03": "Bankruptcy",
    "1.05": "Cybersecurity incident",
    "2.01": "Acquisition/disposal completed",
    "2.02": "Earnings results",
    "2.03": "New debt obligation",
    "2.05": "Restructuring/exit costs",
    "2.06": "Impairment",
    "3.01": "Delisting notice",
    "3.02": "Unregistered share sale",
    "4.01": "Auditor change",
    "4.02": "Prior financials unreliable",
    "5.01": "Change in control",
    "5.02": "Executive/director change",
    "5.03": "Bylaw/fiscal-year change",
    "5.07": "Shareholder vote results",
    "7.01": "Reg FD disclosure",
    "8.01": "Other material event",
    "9.01": "Exhibits",
}
HIGH_IMPACT_ITEMS = {"1.01", "1.03", "1.05", "2.01", "2.02", "2.05", "2.06", "3.01", "4.02", "5.01", "5.02"}


def _get(url: str) -> requests.Response:
    global _last_call
    wait = 0.12 - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()
    r = requests.get(url, headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}, timeout=20)
    r.raise_for_status()
    return r


def get_cik(ticker: str) -> int | None:
    ticker = ticker.upper()
    mapping = {}
    if _CIK_CACHE.exists() and (time.time() - _CIK_CACHE.stat().st_mtime) < 7 * 86400:
        mapping = json.loads(_CIK_CACHE.read_text())
    if ticker not in mapping:
        raw = _get(TICKER_MAP_URL).json()
        mapping = {row["ticker"].upper(): int(row["cik_str"]) for row in raw.values()}
        _CIK_CACHE.parent.mkdir(exist_ok=True)
        _CIK_CACHE.write_text(json.dumps(mapping))
    return mapping.get(ticker)


def recent_filings(cik: int, forms: set[str], since: date) -> list[dict]:
    """Filings of the given form types filed on or after `since`, newest first."""
    data = _get(SUBMISSIONS_URL.format(cik=cik)).json()
    return parse_submissions(data, forms, since)


def parse_submissions(data: dict, forms: set[str], since: date) -> list[dict]:
    recent = data.get("filings", {}).get("recent", {})
    out = []
    for i, form in enumerate(recent.get("form", [])):
        if form not in forms:
            continue
        filed = datetime.strptime(recent["filingDate"][i], "%Y-%m-%d").date()
        if filed < since:
            continue
        acc = recent["accessionNumber"][i]
        out.append({
            "form": form,
            "filed": filed.isoformat(),
            "accepted": (recent.get("acceptanceDateTime") or [""] * (i + 1))[i],
            "accession": acc,
            "primary_doc": recent["primaryDocument"][i],
            "items": [x.strip() for x in (recent.get("items") or [""] * (i + 1))[i].split(",") if x.strip()],
        })
    return out


def filing_url(cik: int, accession: str, doc: str = "") -> str:
    acc = accession.replace("-", "")
    if not doc:
        return FILING_INDEX_URL.format(cik=cik, acc=acc)
    return ARCHIVE_URL.format(cik=cik, acc=acc, doc=doc)


# ---------------------------------------------------------------- Form 4

def _text(node, path):
    el = node.find(path)
    if el is None:
        return ""
    val = el.find("value")
    return ((val.text if val is not None else el.text) or "").strip()


def _flag(node, path) -> bool:
    return _text(node, path).lower() in {"1", "true"}


def parse_form4(xml_text: str) -> list[dict]:
    """Non-derivative transactions from a Form 4 XML document."""
    root = ET.fromstring(xml_text)
    owner = root.find("reportingOwner")
    name = _text(owner, "reportingOwnerId/rptOwnerName") if owner is not None else "Unknown"
    rel = owner.find("reportingOwnerRelationship") if owner is not None else None
    is_director = rel is not None and _flag(rel, "isDirector")
    is_officer = rel is not None and _flag(rel, "isOfficer")
    title = _text(rel, "officerTitle") if rel is not None else ""
    plan_10b5_1 = _flag(root, "aff10b5One")

    txns = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _text(t, "transactionCoding/transactionCode")
        try:
            shares = float(_text(t, "transactionAmounts/transactionShares") or 0)
            price = float(_text(t, "transactionAmounts/transactionPricePerShare") or 0)
        except ValueError:
            shares, price = 0.0, 0.0
        txns.append({
            "insider": name,
            "title": title or ("Director" if is_director else ""),
            "is_officer": is_officer,
            "is_director": is_director,
            "date": _text(t, "transactionDate"),
            "code": code,  # P = open-market buy, S = open-market sale
            "shares": shares,
            "price": price,
            "value": round(shares * price, 2),
            "plan_10b5_1": plan_10b5_1,
        })
    return txns


def insider_activity(ticker: str, days: int = 90, max_filings: int = 40) -> dict:
    """Open-market insider buying/selling over the last `days` days."""
    cik = get_cik(ticker)
    if not cik:
        return {"ticker": ticker, "error": "CIK not found"}
    since = date.today() - timedelta(days=days)
    txns = []
    for f in recent_filings(cik, {"4"}, since)[:max_filings]:
        doc = f["primary_doc"].split("/")[-1]  # strip xsl rendering prefix -> raw XML
        try:
            txns.extend(parse_form4(_get(filing_url(cik, f["accession"], doc)).text))
        except Exception as e:  # one bad filing shouldn't sink the run
            print(f"[edgar] skip {ticker} {f['accession']}: {e}")
    return summarise_insiders(ticker, txns)


def summarise_insiders(ticker: str, txns: list[dict]) -> dict:
    insiders = [t for t in txns if t["is_officer"] or t["is_director"]]
    buys = [t for t in insiders if t["code"] == "P"]
    # Pre-scheduled 10b5-1 sales carry little information; discretionary ones a bit more.
    sells = [t for t in insiders if t["code"] == "S" and not t["plan_10b5_1"]]
    notable = sorted(buys + sells, key=lambda t: t["value"], reverse=True)[:5]
    return {
        "ticker": ticker,
        "buy_value": round(sum(t["value"] for t in buys), 2),
        "buyers": len({t["insider"] for t in buys}),
        "sell_value": round(sum(t["value"] for t in sells), 2),
        "sellers": len({t["insider"] for t in sells}),
        "notable": [
            f"{t['insider']} ({t['title'] or 'insider'}) {'BUY' if t['code'] == 'P' else 'SELL'} "
            f"{t['shares']:,.0f} @ ${t['price']:.2f} on {t['date']}"
            for t in notable
        ],
    }


def score_insiders(s: dict) -> float:
    """-1..1. Cluster buying (several insiders buying with their own money) is the signal;
    discretionary selling is a weak negative. Grants, option exercises and tax
    withholdings are ignored entirely."""
    if not s or s.get("error"):
        return 0.0
    score = 0.0
    if s["buyers"] >= 3:
        score += 1.0
    elif s["buyers"] == 2:
        score += 0.7
    elif s["buyers"] == 1:
        score += 0.4 if s["buy_value"] >= 100_000 else 0.2
    if s["sellers"] >= 3 and s["buyers"] == 0:
        score -= 0.3
    return max(min(score, 1.0), -1.0)
