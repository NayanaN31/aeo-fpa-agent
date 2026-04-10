"""
AEO FP&A Agent — Step 5: Competitor Intelligence Pipeline
==========================================================
Fetches and extracts key financial metrics from Abercrombie & Fitch (ANF)
and The Gap (GPS) 10-K filings for peer comparison analysis.
Also extracts MD&A management commentary snippets from AEO + peers.

Run: python src/05_competitors.py
Output: data/processed/peers.json
        data/processed/mda_summaries.json
"""

import importlib.util
import json
import re
import time
import warnings
from pathlib import Path

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ── Re-use extraction helpers from 02_extract_financials ─────────────────────
_ext_path = Path(__file__).parent / "02_extract_financials.py"
_spec = importlib.util.spec_from_file_location("extract_financials", _ext_path)
_ext = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ext)

parse_ixbrl_contexts     = _ext.parse_ixbrl_contexts
find_current_year_contexts = _ext.find_current_year_contexts
extract_ixbrl_value      = _ext.extract_ixbrl_value
XBRL_DURATION            = _ext.XBRL_DURATION
XBRL_INSTANT             = _ext.XBRL_INSTANT

# ── Peer company registry ─────────────────────────────────────────────────────
PEERS = {
    # Direct AE brand comps — teen/young-adult specialty apparel
    "ANF":  {"cik": "0001018840", "name": "Abercrombie & Fitch Co.", "years": 6},
    "URBN": {"cik": "0000912615", "name": "Urban Outfitters Inc.",   "years": 6},
    "BKE":  {"cik": "0000885245", "name": "Buckle Inc.",             "years": 6},
    # Aerie-specific comps — activewear / intimates
    "LULU": {"cik": "0001397187", "name": "lululemon athletica",     "years": 6},
    "VSCO": {"cik": "0001856437", "name": "Victoria's Secret & Co.", "years": 4},  # spun off 2021
    # Broader specialty retail benchmark
    "GPS":  {"cik": "0000039911", "name": "The Gap Inc.",            "years": 6},
}

HEADERS  = {"User-Agent": "AEO FPA Research Project research@example.com"}
RAW_DIR  = Path("data/raw/peers")
OUT_DIR  = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Metrics to extract for peers (subset of full AEO extraction)
PEER_DURATION_METRICS = {
    k: v for k, v in XBRL_DURATION.items()
    if k in ("net_revenue", "gross_profit", "sga_expense", "operating_income",
             "net_income", "operating_cash_flow", "capex")
}
PEER_INSTANT_METRICS = {
    k: v for k, v in XBRL_INSTANT.items()
    if k in ("cash_and_equivalents", "total_inventory", "total_assets")
}


# ── EDGAR helpers ─────────────────────────────────────────────────────────────

def get_recent_10k_filings(cik: str, count: int = 6) -> list[dict]:
    """
    Query EDGAR submissions API and return the most recent `count` 10-K filings
    as {label, period_end, url, filing_date}.
    Checks both recent and first overflow page for older filings.
    """
    results = []

    for suffix in ["", "-submissions-001"]:
        url = f"https://data.sec.gov/submissions/CIK{cik}{suffix}.json"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        filings = data if suffix else data["filings"]["recent"]
        if not suffix:
            filings = data["filings"]["recent"]

        forms       = filings.get("form", [])
        dates       = filings.get("filingDate", [])
        accessions  = filings.get("accessionNumber", [])
        primary_docs= filings.get("primaryDocument", [])
        periods     = filings.get("reportDate", dates)

        cik_plain = cik.lstrip("0")
        for i, form in enumerate(forms):
            if form == "10-K" and len(results) < count:
                acc = accessions[i].replace("-", "")
                doc = primary_docs[i]
                period = periods[i] if i < len(periods) and periods[i] else dates[i]
                # Derive fiscal year label from report period (not filing date)
                fy = int(period[:4]) if period else int(dates[i][:4]) - 1
                results.append({
                    "label":       f"FY{fy}",
                    "period_end":  period,
                    "url":         f"https://www.sec.gov/Archives/edgar/data/{cik_plain}/{acc}/{doc}",
                    "filing_date": dates[i],
                })

        if len(results) >= count:
            break
        time.sleep(0.5)

    return results


def fetch_filing(ticker: str, label: str, url: str) -> Path | None:
    """Download a 10-K HTML and save to data/raw/peers/."""
    out = RAW_DIR / f"{ticker}_{label}.html"
    if out.exists():
        print(f"    ✓ {ticker} {label} already cached.")
        return out
    print(f"    ↓ Fetching {ticker} {label} …", end="", flush=True)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        out.write_bytes(resp.content)
        print(f" {len(resp.content)//1024} KB")
        time.sleep(1.2)
        return out
    except Exception as e:
        print(f" ERROR: {e}")
        return None


# ── Financial extraction ──────────────────────────────────────────────────────

def extract_peer_financials(ticker: str, label: str, html_path: Path, period_end: str) -> dict:
    """Extract key financial metrics from a peer 10-K (iXBRL only for simplicity)."""
    with open(html_path, "rb") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    record = {"ticker": ticker, "label": label, "period_end": period_end, "units": "thousands_usd"}

    if not soup.find("ix:nonfraction"):
        return record  # Non-iXBRL — skip for now

    ctx_map = parse_ixbrl_contexts(soup)
    dur_ctxs, inst_ctxs = find_current_year_contexts(ctx_map, period_end)

    for metric, concepts in PEER_DURATION_METRICS.items():
        record[metric] = extract_ixbrl_value(soup, concepts, dur_ctxs)

    for metric, concepts in PEER_INSTANT_METRICS.items():
        record[metric] = extract_ixbrl_value(soup, concepts, inst_ctxs)

    rev = record.get("net_revenue")
    gp  = record.get("gross_profit")
    oi  = record.get("operating_income")
    ocf = record.get("operating_cash_flow")
    cap = record.get("capex")

    if rev and gp:
        record["gross_margin_pct"]    = round(gp / rev * 100, 2)
    if rev and oi:
        record["operating_margin_pct"]= round(oi / rev * 100, 2)
    if ocf and cap:
        record["free_cash_flow"]      = ocf - abs(cap)

    return record


# ── MD&A extraction ───────────────────────────────────────────────────────────

def extract_mda_summary(html_path: Path, max_chars: int = 900) -> str:
    """
    Find the MD&A section and return an opening-paragraph summary.
    Focuses on the first substantive block after the section heading.
    """
    with open(html_path, "rb") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    # Locate the MD&A section
    patterns = [
        r"MANAGEMENT.S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION",
        r"Management.s Discussion and Analysis of Financial Condition",
        r"ITEM\s+7[A-Z\.\s]*MANAGEMENT",
    ]
    start = -1
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            start = m.end()
            break

    if start == -1:
        return ""

    chunk = text[start: start + 3000]

    # Skip boilerplate "Overview" / table-of-contents lines (short sentences)
    sentences = re.split(r"(?<=[.!?])\s+", chunk)
    good = [s for s in sentences if len(s) > 60]
    body = " ".join(good)

    if len(body) > max_chars:
        cut = body.rfind(".", 0, max_chars)
        body = body[: cut + 1] if cut > 0 else body[:max_chars]

    return body.strip()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n=== Competitor Intelligence Pipeline ===\n")

    peer_records  = []
    mda_summaries = {}

    # ── Peer financials ───────────────────────────────────────────────────────
    for ticker, info in PEERS.items():
        print(f"── {ticker}: {info['name']} ──")
        filings = get_recent_10k_filings(info["cik"], count=info["years"])
        print(f"   Found {len(filings)} filings\n")

        for f in filings:
            html = fetch_filing(ticker, f["label"], f["url"])
            if not html:
                continue
            rec = extract_peer_financials(ticker, f["label"], html, f["period_end"])
            peer_records.append(rec)

            rev = rec.get("net_revenue") or 0
            gm  = rec.get("gross_margin_pct") or 0
            om  = rec.get("operating_margin_pct") or 0
            print(f"    {ticker} {f['label']}: Rev ${rev/1e6:.1f}B | GM {gm:.1f}% | OM {om:.1f}%")

            mda = extract_mda_summary(html)
            if mda:
                mda_summaries[f"{ticker}_{f['label']}"] = mda

        print()

    # ── AEO MD&A ──────────────────────────────────────────────────────────────
    print("── AEO: Extracting MD&A commentary ──")
    for html_path in sorted(Path("data/raw").glob("FY*.html")):
        label = html_path.stem
        mda   = extract_mda_summary(html_path)
        if mda:
            mda_summaries[f"AEO_{label}"] = mda
            print(f"    AEO {label}: {len(mda)} chars")

    # ── Save outputs ──────────────────────────────────────────────────────────
    peers_path = OUT_DIR / "peers.json"
    with open(peers_path, "w") as f:
        json.dump(peer_records, f, indent=2)
    print(f"\n✓ Peer data  → {peers_path}  ({len(peer_records)} records)")

    mda_path = OUT_DIR / "mda_summaries.json"
    with open(mda_path, "w") as f:
        json.dump(mda_summaries, f, indent=2)
    print(f"✓ MD&A data  → {mda_path}  ({len(mda_summaries)} entries)")
    print("\nNext: restart the API server to load the new context.")


if __name__ == "__main__":
    main()
