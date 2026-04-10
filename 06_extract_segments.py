"""
AEO FP&A Agent — Step 6: Extract Brand Segment Financials
==========================================================
Extracts AE brand vs Aerie brand revenue and operating income
from iXBRL contexts in the 10-K filings (FY2020–FY2024).

Segment XBRL dimensions:
  Aerie: dimension="us-gaap:StatementBusinessSegmentsAxis" member="aeo:AerieBrandMember"
  AE:    dimension="us-gaap:StatementBusinessSegmentsAxis" member="aeo:AmericanEagleBrandMember"

Run: python src/06_extract_segments.py
Input:  data/raw/FY20*.html
Output: data/processed/aeo_segments.json
"""

import json
import warnings
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FISCAL_YEAR_META = {
    "FY2020": {"fiscal_year": 2020, "period_end": "2021-01-30"},
    "FY2021": {"fiscal_year": 2021, "period_end": "2022-01-29"},
    "FY2022": {"fiscal_year": 2022, "period_end": "2023-01-28"},
    "FY2023": {"fiscal_year": 2023, "period_end": "2024-02-03"},
    "FY2024": {"fiscal_year": 2024, "period_end": "2025-02-01"},
}

# The segment concepts available in AEO's XBRL filings
REV_CONCEPT = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
OI_CONCEPT  = "aeo:SegmentOperatingIncome"

SEGMENT_MEMBERS = {
    "aerie": "aeo:AerieBrandMember",
    "ae":    "aeo:AmericanEagleBrandMember",
}


def _parse_xbrl_value(tag) -> float | None:
    """Return a normalized-to-thousands float from an ix:nonfraction tag."""
    if tag is None:
        return None
    raw = tag.get_text(strip=True).replace(",", "").replace("$", "").replace(" ", "")
    if not raw:
        return None
    negative = (tag.get("sign") == "-") or (raw.startswith("(") and raw.endswith(")"))
    raw = raw.replace("(", "").replace(")", "")
    try:
        val = float(raw)
        try:
            dec = int(tag.get("decimals", "-3"))
            if dec == -6:
                val *= 1_000
            elif dec == -9:
                val *= 1_000_000
        except (ValueError, TypeError):
            pass
        return -val if negative else val
    except ValueError:
        return None


def _find_segment_contexts(soup: BeautifulSoup, member: str) -> dict[str, dict]:
    """
    Return {ctx_id: {start, end, span_days}} for all duration contexts
    that contain the given segment member and span >= 350 days.
    """
    result = {}
    for ctx in soup.find_all("xbrli:context"):
        txt = str(ctx)
        if member not in txt:
            continue
        period = ctx.find("xbrli:period")
        if not period:
            continue
        start_tag = period.find("xbrli:startdate")
        end_tag   = period.find("xbrli:enddate")
        if not (start_tag and end_tag):
            continue
        s = start_tag.get_text(strip=True)
        e = end_tag.get_text(strip=True)
        try:
            span = (date.fromisoformat(e) - date.fromisoformat(s)).days
        except ValueError:
            continue
        if span >= 350:
            result[ctx.get("id", "")] = {"start": s, "end": e, "span_days": span}
    return result


def extract_segment_row(soup: BeautifulSoup, member: str, target_start: str, target_end: str) -> dict:
    """
    Find the full-year duration context for this segment member that matches
    the target period, then extract revenue and operating income.
    """
    seg_ctxs = _find_segment_contexts(soup, member)
    # Pick the context whose period best matches target
    best_ctx = None
    best_score = -1
    for cid, info in seg_ctxs.items():
        score = (info["end"] == target_end) * 2 + (info["start"] == target_start)
        if score > best_score:
            best_score = score
            best_ctx = cid
    if best_ctx is None:
        return {"revenue": None, "operating_income": None}

    rev_tag = soup.find("ix:nonfraction", attrs={"name": REV_CONCEPT, "contextref": best_ctx})
    oi_tag  = soup.find("ix:nonfraction", attrs={"name": OI_CONCEPT,  "contextref": best_ctx})
    return {
        "revenue":          _parse_xbrl_value(rev_tag),
        "operating_income": _parse_xbrl_value(oi_tag),
        "_ctx":             best_ctx,
        "_period":          f"{seg_ctxs[best_ctx]['start']}→{seg_ctxs[best_ctx]['end']}",
    }


def extract_all_historical_segments(soup: BeautifulSoup) -> dict[str, dict[str, dict]]:
    """
    Extract ALL available segment rows from a single filing, keyed by period end date.
    A 10-K typically contains 2-3 years of comparative data.
    """
    results: dict[str, dict[str, dict]] = {}  # period_end → {aerie: {...}, ae: {...}}

    for brand, member in SEGMENT_MEMBERS.items():
        seg_ctxs = _find_segment_contexts(soup, member)
        for cid, info in seg_ctxs.items():
            end_date = info["end"]
            results.setdefault(end_date, {})
            rev_tag = soup.find("ix:nonfraction", attrs={"name": REV_CONCEPT, "contextref": cid})
            oi_tag  = soup.find("ix:nonfraction", attrs={"name": OI_CONCEPT,  "contextref": cid})
            rev = _parse_xbrl_value(rev_tag)
            oi  = _parse_xbrl_value(oi_tag)
            # Only update if we found at least revenue (avoid overwriting good data with None)
            if rev is not None or oi is not None:
                existing = results[end_date].get(brand, {})
                if rev is not None:
                    existing["revenue"] = rev
                if oi is not None:
                    existing["operating_income"] = oi
                results[end_date][brand] = existing

    return results


# Map period end dates to fiscal year labels (AEO fiscal calendar)
PERIOD_END_TO_LABEL = {
    "2019-02-02": "FY2018",
    "2020-02-01": "FY2019",
    "2021-01-30": "FY2020",
    "2022-01-29": "FY2021",
    "2023-01-28": "FY2022",
    "2024-02-03": "FY2023",
    "2025-02-01": "FY2024",
}


def main():
    # Accumulate all segment observations; later filings override earlier for the same FY
    # (later filings have more complete data, including OI which isn't in older filings)
    all_segments: dict[str, dict] = {}  # label → {aerie: {...}, ae: {...}}

    for label in sorted(FISCAL_YEAR_META.keys()):
        html_path = RAW_DIR / f"{label}.html"
        if not html_path.exists():
            print(f"  {label}: raw file not found — skipping")
            continue

        print(f"Processing {label}…")
        with open(html_path, "rb") as f:
            soup = BeautifulSoup(f.read(), "lxml")

        if not soup.find("ix:nonfraction"):
            print(f"  {label}: not iXBRL — skipping segment extraction")
            continue

        year_data = extract_all_historical_segments(soup)
        for period_end, brands in year_data.items():
            fy_label = PERIOD_END_TO_LABEL.get(period_end)
            if not fy_label:
                continue
            existing = all_segments.get(fy_label, {})
            for brand, metrics in brands.items():
                if brand not in existing:
                    existing[brand] = {}
                existing[brand].update({k: v for k, v in metrics.items() if v is not None})
            all_segments[fy_label] = existing

    # Build final sorted records
    records = []
    label_order = ["FY2018", "FY2019", "FY2020", "FY2021", "FY2022", "FY2023", "FY2024"]
    for lbl in label_order:
        if lbl not in all_segments:
            continue
        data   = all_segments[lbl]
        aerie  = data.get("aerie", {})
        ae     = data.get("ae", {})

        aerie_rev = aerie.get("revenue")
        ae_rev    = ae.get("revenue")
        total_rev = (aerie_rev or 0) + (ae_rev or 0)

        rec = {
            "label":               lbl,
            "aerie_revenue":       aerie_rev,
            "ae_revenue":          ae_rev,
            "aerie_oi":            aerie.get("operating_income"),
            "ae_oi":               ae.get("operating_income"),
            "aerie_share_pct":     round(aerie_rev / total_rev * 100, 1) if (aerie_rev and total_rev) else None,
            "aerie_oi_margin_pct": round(aerie.get("operating_income", 0) / aerie_rev * 100, 1)
                                   if (aerie.get("operating_income") and aerie_rev) else None,
            "ae_oi_margin_pct":    round(ae.get("operating_income", 0) / ae_rev * 100, 1)
                                   if (ae.get("operating_income") and ae_rev) else None,
            "units":               "thousands_usd",
        }
        records.append(rec)
        print(f"  {lbl}: Aerie=${aerie_rev:,.0f}K ({rec['aerie_share_pct']}%), AE=${ae_rev:,.0f}K" if aerie_rev and ae_rev else f"  {lbl}: incomplete")

    out_path = OUT_DIR / "aeo_segments.json"
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)
    print(f"\nSaved {len(records)} segment records → {out_path}")


if __name__ == "__main__":
    main()
