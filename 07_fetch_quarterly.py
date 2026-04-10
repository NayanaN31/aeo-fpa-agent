"""
AEO FP&A Agent — Step 7: Fetch Quarterly Financials from SEC EDGAR XBRL API
=============================================================================
Pulls quarterly P&L data for AEO directly from the structured XBRL API.
No HTML parsing needed — one API call returns all historical quarterly facts.

Run: python src/07_fetch_quarterly.py
Output: data/processed/aeo_quarterly.json
"""

import json
import requests
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "aeo_quarterly.json"

CIK = "0000919012"
XBRL_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
HEADERS = {"User-Agent": "AEO-FPA-Agent research@example.com"}

CONCEPT_MAP = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": "net_revenue",
    "SalesRevenueGoodsNet": "net_revenue_legacy",
    "CostOfGoodsAndServicesSold": "cogs",
    "CostOfRevenue": "cogs_legacy",
    "GrossProfit": "gross_profit",
    "SellingGeneralAndAdministrativeExpense": "sga_expense",
    "OperatingIncomeLoss": "operating_income",
    "NetIncomeLoss": "net_income",
    "DepreciationAndAmortization": "depreciation",
}


def _parse_frame(frame: str) -> tuple[int, int] | None:
    """Parse 'CY2024Q3' → (2024, 3). Returns None if not a single-quarter frame."""
    if not frame or not frame.startswith("CY") or "Q" not in frame:
        return None
    try:
        parts = frame.replace("CY", "").split("Q")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None


def _aeo_fiscal_year(cal_year: int, cal_quarter: int) -> tuple[int, int]:
    """
    AEO fiscal year ends in late January/early February.
    CY Q1 (Feb-Apr) = FY Q1, CY Q2 (May-Jul) = FY Q2,
    CY Q3 (Aug-Oct) = FY Q3, CY Q4 (Nov-Jan) = FY Q4.
    FY2024 = Feb 2024 – Feb 2025.
    """
    return cal_year, cal_quarter


def fetch_quarterly() -> list[dict]:
    print(f"Fetching XBRL data from {XBRL_URL} ...")
    resp = requests.get(XBRL_URL, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    us_gaap = data.get("facts", {}).get("us-gaap", {})

    quarters: dict[str, dict] = defaultdict(dict)

    for xbrl_concept, field_name in CONCEPT_MAP.items():
        if xbrl_concept not in us_gaap:
            continue
        entries = us_gaap[xbrl_concept].get("units", {}).get("USD", [])

        for entry in entries:
            parsed = _parse_frame(entry.get("frame", ""))
            if not parsed:
                continue
            cal_year, cal_q = parsed
            fy, fq = _aeo_fiscal_year(cal_year, cal_q)
            key = f"FY{fy}Q{fq}"

            # Prefer newer concept over legacy
            if field_name.endswith("_legacy"):
                base_field = field_name.replace("_legacy", "")
                if base_field in quarters[key]:
                    continue
                quarters[key][base_field] = entry["val"]
            else:
                quarters[key][field_name] = entry["val"]

            quarters[key]["fiscal_year"] = fy
            quarters[key]["fiscal_quarter"] = fq
            quarters[key]["label"] = key
            quarters[key]["period_end"] = entry.get("end", "")

    records = []
    for key in sorted(quarters.keys()):
        q = quarters[key]
        rev = q.get("net_revenue", 0)
        gp  = q.get("gross_profit", 0)
        oi  = q.get("operating_income", 0)

        if rev > 0:
            q["gross_margin_pct"] = round(gp / rev * 100, 2) if gp else None
            q["operating_margin_pct"] = round(oi / rev * 100, 2) if oi else None
            q["sga_pct_of_revenue"] = round(q.get("sga_expense", 0) / rev * 100, 2) if q.get("sga_expense") else None

        records.append(q)

    # Filter to reasonable range (FY2018+)
    records = [r for r in records if r.get("fiscal_year", 0) >= 2018]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(records, f, indent=2)

    print(f"\nExtracted {len(records)} quarterly records → {OUTPUT_PATH}")
    for r in records[-8:]:
        rev_m = r.get("net_revenue", 0) / 1e6
        gm = r.get("gross_margin_pct", "?")
        om = r.get("operating_margin_pct", "?")
        print(f"  {r['label']}: Rev ${rev_m:,.0f}M | GM {gm}% | OM {om}%")

    return records


if __name__ == "__main__":
    fetch_quarterly()
