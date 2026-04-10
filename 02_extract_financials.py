"""
AEO FP&A Agent — Step 2: Extract Structured Financial Data from 10-K HTML
==========================================================================
Parses downloaded HTML filings and extracts the key financial metrics needed
for the FP&A agent. Outputs a single clean CSV and JSON file.

Supports two filing formats:
  - Plain HTML tables (FY2015–FY2019): row-text search across all tables
  - iXBRL inline XBRL (FY2020–FY2024): semantic extraction via XBRL concept names

Run: python src/02_extract_financials.py
Input:  data/raw/*.html
Output: data/processed/aeo_financials.csv
        data/processed/aeo_financials.json
"""

import json
import re
import warnings
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Financial metrics we want to extract
# Organized by the section of the 10-K where they appear
# ---------------------------------------------------------------------------
TARGET_METRICS = {
    # Income Statement
    "net_revenue": ["net revenue", "total net revenue", "total revenues"],
    "cost_of_sales": ["cost of sales", "cost of goods sold", "cogs"],
    "gross_profit": ["gross profit"],
    "gross_margin_pct": None,  # Computed: gross_profit / net_revenue
    "sga_expense": ["selling, general and administrative", "sg&a", "sga"],
    "operating_income": ["operating income", "income from operations"],
    "operating_margin_pct": None,  # Computed
    "net_income": ["net income", "net earnings"],
    "diluted_eps": ["diluted earnings per share", "diluted eps"],

    # Balance Sheet
    "total_assets": ["total assets"],
    "total_inventory": ["inventories", "merchandise inventories"],
    "total_debt": ["long-term debt", "long term debt", "total debt"],
    "cash_and_equivalents": ["cash and cash equivalents"],
    "shareholders_equity": ["total stockholders' equity", "total shareholders equity"],

    # Cash Flow
    "operating_cash_flow": ["net cash provided by operating activities", "cash from operations"],
    "capex": ["capital expenditures", "purchases of property and equipment"],
    "free_cash_flow": None,  # Computed: operating_cash_flow - capex

    # Retail-specific KPIs (from MD&A section)
    "comparable_sales_change": ["comparable sales", "comparable store sales", "comp sales"],
    "total_stores": ["number of stores", "total stores", "stores operated"],
    "revenue_per_store": None,  # Computed
}

# Fiscal year metadata — maps filename label to metadata
FISCAL_YEAR_META = {
    "FY2015": {"fiscal_year": 2015, "period_end": "2016-01-30"},
    "FY2016": {"fiscal_year": 2016, "period_end": "2017-01-28"},
    "FY2017": {"fiscal_year": 2017, "period_end": "2018-02-03"},
    "FY2018": {"fiscal_year": 2018, "period_end": "2019-02-02"},
    "FY2019": {"fiscal_year": 2019, "period_end": "2020-02-01"},
    "FY2020": {"fiscal_year": 2020, "period_end": "2021-01-30"},
    "FY2021": {"fiscal_year": 2021, "period_end": "2022-01-29"},
    "FY2022": {"fiscal_year": 2022, "period_end": "2023-01-28"},
    "FY2023": {"fiscal_year": 2023, "period_end": "2024-02-03"},
    "FY2024": {"fiscal_year": 2024, "period_end": "2025-02-01"},
}


# ---------------------------------------------------------------------------
# iXBRL concept maps — used for FY2020+ filings
# Each entry maps our internal metric name to a list of US-GAAP concept names
# to try in order. Duration = income statement / cash flow. Instant = balance sheet.
# ---------------------------------------------------------------------------
XBRL_DURATION = {
    "net_revenue":        ["us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "us-gaap:Revenues", "us-gaap:SalesRevenueNet"],
    "cost_of_sales":      ["us-gaap:CostOfGoodsAndServicesSold", "us-gaap:CostOfRevenue"],
    "gross_profit":       ["us-gaap:GrossProfit"],
    "sga_expense":        ["us-gaap:SellingGeneralAndAdministrativeExpense"],
    "operating_income":   ["us-gaap:OperatingIncomeLoss"],
    "net_income":         ["us-gaap:NetIncomeLoss"],
    "diluted_eps":        ["us-gaap:EarningsPerShareDiluted"],
    "operating_cash_flow":["us-gaap:NetCashProvidedByUsedInOperatingActivities"],
    "capex":              ["us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"],
}

XBRL_INSTANT = {
    "cash_and_equivalents": ["us-gaap:CashAndCashEquivalentsAtCarryingValue"],
    "total_inventory":      ["us-gaap:InventoryNet"],
    "total_assets":         ["us-gaap:Assets"],
    "total_debt":           ["us-gaap:LongTermDebt", "us-gaap:DebtAndCapitalLeaseObligations"],
    "shareholders_equity":  ["us-gaap:StockholdersEquity"],
    "total_stores":         ["us-gaap:NumberOfStores"],
}


def parse_ixbrl_contexts(soup: BeautifulSoup) -> dict:
    """
    Build a map of contextRef -> {type, date/start/end, has_segment}.
    type is 'instant' or 'duration'.
    """
    ctx_map = {}
    for ctx in soup.find_all("xbrli:context"):
        cid = ctx.get("id", "")
        has_segment = ctx.find("xbrli:segment") is not None
        period = ctx.find("xbrli:period")
        if not period:
            continue
        instant = period.find("xbrli:instant")
        if instant:
            ctx_map[cid] = {"type": "instant", "date": instant.get_text(strip=True), "has_segment": has_segment}
        else:
            start = period.find("xbrli:startdate")
            end = period.find("xbrli:enddate")
            if start and end:
                ctx_map[cid] = {
                    "type": "duration",
                    "start": start.get_text(strip=True),
                    "end": end.get_text(strip=True),
                    "has_segment": has_segment,
                }
    return ctx_map


def find_current_year_contexts(ctx_map: dict, period_end: str) -> tuple[list[str], list[str]]:
    """
    Given context map and the filing's period_end date, return
    (duration_ctx_ids, instant_ctx_ids) for the current fiscal year
    (consolidated — no segment dimension).

    Returns ALL unsegmented contexts ending on period_end, with full-year
    duration contexts (>= 350 days) sorted longest-first. Callers try
    each candidate in order so that metrics split across multiple contexts
    are still found.
    """
    from datetime import date

    instant_ctxs = []
    duration_candidates = []  # list of (span_days, cid)

    end_date = date.fromisoformat(period_end)

    for cid, info in ctx_map.items():
        if info.get("has_segment"):
            continue
        if info["type"] == "instant" and info["date"] == period_end:
            instant_ctxs.append(cid)
        if info["type"] == "duration" and info.get("end") == period_end:
            start_date = date.fromisoformat(info["start"])
            span_days = (end_date - start_date).days
            if span_days >= 350:  # full fiscal year (52-53 weeks)
                duration_candidates.append((span_days, cid))

    duration_candidates.sort(reverse=True)
    duration_ctxs = [cid for _, cid in duration_candidates]
    return duration_ctxs, instant_ctxs


def extract_ixbrl_value(soup: BeautifulSoup, concepts: list[str], ctx_ids: list[str]) -> float | None:
    """
    Find the first matching ix:nonfraction tag for any of the given concepts
    across all provided context IDs, and return its numeric value normalized
    to thousands USD (our standard unit).

    Handles:
    - sign="-" attribute and parenthetical negatives
    - decimals attribute for scale normalization:
        decimals=-3  → already in thousands (AEO standard)
        decimals=-6  → millions → multiply by 1,000
        decimals=-9  → billions → multiply by 1,000,000
    """
    for ctx_id in ctx_ids:
        for concept in concepts:
            tags = soup.find_all("ix:nonfraction", attrs={"name": concept, "contextref": ctx_id})
            for tag in tags:
                raw = tag.get_text(strip=True).replace(",", "").replace("$", "").replace(" ", "")
                if not raw:
                    continue
                negative = (tag.get("sign") == "-") or (raw.startswith("(") and raw.endswith(")"))
                raw = raw.replace("(", "").replace(")", "")
                try:
                    val = float(raw)
                    # Normalize to thousands USD
                    try:
                        dec = int(tag.get("decimals", "-3"))
                        if dec == -6:
                            val *= 1_000        # millions → thousands
                        elif dec == -9:
                            val *= 1_000_000    # billions → thousands
                        # dec == -3 or positive (EPS etc.): no scale change
                    except (ValueError, TypeError):
                        pass
                    return -val if negative else val
                except ValueError:
                    continue
    return None


def extract_filing_ixbrl(label: str, html_path: Path, period_end: str) -> dict | None:
    """
    Extract financial metrics from an iXBRL-formatted 10-K filing.
    Returns a partial record dict, or None if not an iXBRL file.
    """
    with open(html_path, "rb") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    if not soup.find("ix:nonfraction"):
        return None  # Not an iXBRL file — fall through to table extraction

    print(f"    Detected iXBRL format — using semantic extraction.")
    ctx_map = parse_ixbrl_contexts(soup)
    dur_ctxs, inst_ctxs = find_current_year_contexts(ctx_map, period_end)
    print(f"    Duration contexts ({len(dur_ctxs)}): {dur_ctxs[:2]}")
    print(f"    Instant  contexts ({len(inst_ctxs)}): {inst_ctxs[:2]}")

    record = {}

    for metric, concepts in XBRL_DURATION.items():
        record[metric] = extract_ixbrl_value(soup, concepts, dur_ctxs)

    for metric, concepts in XBRL_INSTANT.items():
        record[metric] = extract_ixbrl_value(soup, concepts, inst_ctxs)

    # Comparable sales % is narrative text — fall back to regex regardless of format
    record["comparable_sales_change"] = extract_from_text_patterns(html_path, "comparable_sales_change")

    return record


def clean_number(text: str) -> float | None:
    """
    Convert a string like '$4,284,749' or '(143,241)' to a float.
    Parentheses = negative (standard accounting notation).
    Values in 10-Ks are typically in thousands unless otherwise noted.
    """
    if not text:
        return None
    text = text.strip().replace("$", "").replace(",", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.replace("(", "").replace(")", "")
    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return None


def extract_tables_from_html(html_path: Path) -> list[pd.DataFrame]:
    """Parse all HTML tables from a 10-K filing."""
    with open(html_path, "rb") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            try:
                df = pd.DataFrame(rows)
                tables.append(df)
            except Exception:
                pass
    return tables


def find_metric_in_tables(
    tables: list[pd.DataFrame], search_terms: list[str]
) -> float | None:
    """
    Search all tables for a row matching any of the search terms,
    then return the most recent year's value (typically column 1 or 2).
    """
    for term in search_terms:
        for df in tables:
            for idx, row in df.iterrows():
                # Check all cells in the row for the search term
                row_text = " ".join(str(c) for c in row.values).lower()
                if term.lower() in row_text:
                    # Find the first numeric value in the row (skip the label column)
                    for col_idx in range(1, min(4, len(row))):
                        val = clean_number(str(row.iloc[col_idx]))
                        if val is not None and abs(val) > 0:
                            return val
    return None


def extract_from_text_patterns(html_path: Path, metric: str) -> float | None:
    """
    Fallback: use regex on raw text for metrics that don't parse cleanly from tables.
    Useful for comparable sales % which is often in the MD&A narrative.
    """
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    soup = BeautifulSoup(text, "lxml")
    plain_text = soup.get_text(separator=" ")

    if metric == "comparable_sales_change":
        # Match patterns like "comparable sales increased 3%" or "comp sales of (2)%"
        patterns = [
            r"comparable sales (?:increased|decreased|changed|grew)[^\d\-\(]*(\(?\d+\.?\d*\)?)\s*%",
            r"comp (?:store )?sales[^\d\-\(]*(\(?\d+\.?\d*\)?)\s*%",
            r"comparable store sales[^\d\-\(]*(\(?\d+\.?\d*\)?)\s*%",
        ]
        for pattern in patterns:
            match = re.search(pattern, plain_text, re.IGNORECASE)
            if match:
                return clean_number(match.group(1))

    if metric == "total_stores":
        # Match "operated X stores" or "X retail stores"
        patterns = [
            r"operated\s+(\d[,\d]*)\s+(?:retail\s+)?stores",
            r"(\d[,\d]*)\s+(?:total\s+)?(?:retail\s+)?stores",
            r"(\d[,\d]*)\s+AE\s+stores",
        ]
        for pattern in patterns:
            match = re.search(pattern, plain_text, re.IGNORECASE)
            if match:
                val = clean_number(match.group(1))
                if val and 500 < val < 3000:  # Sanity check for store count
                    return val

    return None


def extract_filing_data(label: str, html_path: Path) -> dict:
    """
    Main extraction function for a single 10-K filing.
    Tries iXBRL semantic extraction first; falls back to HTML table parsing.
    Returns a dictionary of financial metrics.
    """
    print(f"  Parsing {label}...")
    meta = FISCAL_YEAR_META.get(label, {})
    period_end = meta.get("period_end", "")
    record = {
        "label": label,
        "fiscal_year": meta.get("fiscal_year"),
        "period_end": period_end,
    }

    # --- Try iXBRL extraction first (FY2020+) ---
    ixbrl_data = extract_filing_ixbrl(label, html_path, period_end)
    if ixbrl_data is not None:
        record.update(ixbrl_data)
        # Fill in None for any metrics not covered by iXBRL map
        for metric in TARGET_METRICS:
            if metric not in record:
                record[metric] = None
    else:
        # --- Plain HTML table extraction (FY2015–FY2019) ---
        tables = extract_tables_from_html(html_path)
        print(f"    Found {len(tables)} tables in filing.")

        for metric, search_terms in TARGET_METRICS.items():
            if search_terms is None:
                record[metric] = None
                continue
            val = find_metric_in_tables(tables, search_terms)
            if val is None:
                val = extract_from_text_patterns(html_path, metric)
            record[metric] = val

    # --- Computed metrics ---
    rev = record.get("net_revenue")
    gp = record.get("gross_profit")
    oi = record.get("operating_income")
    ocf = record.get("operating_cash_flow")
    capex = record.get("capex")
    stores = record.get("total_stores")

    if rev and gp:
        record["gross_margin_pct"] = round(gp / rev * 100, 2)
    if rev and oi:
        record["operating_margin_pct"] = round(oi / rev * 100, 2)
    if ocf and capex:
        record["free_cash_flow"] = ocf - abs(capex)  # capex is often negative in filings
    if rev and stores and stores > 0:
        record["revenue_per_store"] = round(rev / stores, 1)

    # --- Units note ---
    # 10-K financials are reported in thousands. We'll keep that convention.
    # net_revenue of 4,284,749 means $4.28 billion.
    record["units"] = "thousands_usd"

    return record


def main():
    print("\n=== AEO Financial Extractor ===\n")

    raw_files = sorted(RAW_DIR.glob("FY*.html"))
    if not raw_files:
        print("ERROR: No HTML files found in data/raw/")
        print("Run python src/01_fetch_filings.py first.")
        return

    print(f"Found {len(raw_files)} filing(s): {[f.stem for f in raw_files]}\n")

    records = []
    for html_path in raw_files:
        label = html_path.stem
        try:
            record = extract_filing_data(label, html_path)
            records.append(record)
        except Exception as e:
            print(f"  ERROR processing {label}: {e}")

    if not records:
        print("No records extracted. Check that HTML files are valid 10-K filings.")
        return

    # Sort by fiscal year
    records.sort(key=lambda r: r.get("fiscal_year", 0))

    # --- Save CSV ---
    df = pd.DataFrame(records)
    csv_path = OUT_DIR / "aeo_financials.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n✓ CSV saved: {csv_path}")

    # --- Save JSON (more readable for the agent) ---
    json_path = OUT_DIR / "aeo_financials.json"
    with open(json_path, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"✓ JSON saved: {json_path}")

    # --- Print preview ---
    print("\n--- Extraction Preview ---")
    key_cols = ["label", "net_revenue", "gross_margin_pct", "operating_margin_pct",
                "operating_income", "comparable_sales_change", "total_stores"]
    available_cols = [c for c in key_cols if c in df.columns]
    print(df[available_cols].to_string(index=False))
    print("\nNext step: run  python src/03_build_agent.py")


if __name__ == "__main__":
    main()
