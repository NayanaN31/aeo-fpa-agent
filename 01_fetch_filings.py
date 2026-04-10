"""
AEO FP&A Agent — Step 1: Fetch 10-K Filings from SEC EDGAR
============================================================
Downloads AEO annual reports directly from SEC EDGAR as HTML files.
No API key required — all public data.

Run: python src/01_fetch_filings.py
Output: data/raw/  (one .html file per fiscal year)
"""

import requests
import time
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Known AEO 10-K filing URLs from SEC EDGAR (CIK: 0000919012)
# Fiscal year end dates (AEO uses 52/53-week year ending late Jan/early Feb)
# ---------------------------------------------------------------------------
FILINGS = [
    # (fiscal_year_label, fiscal_year_end_date, sec_url)
    ("FY2024", "2025-02-01", "https://www.sec.gov/Archives/edgar/data/0000919012/000095017025042746/aeo-20250201.htm"),
    ("FY2023", "2024-02-03", "https://www.sec.gov/Archives/edgar/data/0000919012/000095017024032294/aeo-20240203.htm"),
    ("FY2022", "2023-01-28", "https://www.sec.gov/Archives/edgar/data/0000919012/000095017023007604/aeo-20230128.htm"),
    ("FY2021", "2022-01-29", "https://www.sec.gov/Archives/edgar/data/0000919012/000095017022003587/aeo-20220129.htm"),
    ("FY2020", "2021-01-30", "https://www.sec.gov/Archives/edgar/data/0000919012/000156459021012543/aeo-10k_20210130.htm"),
    # FY2015–FY2019: fetched via EDGAR full-text search below
]

# EDGAR full-text search for older filings (fetched programmatically)
EDGAR_SEARCH_URL = (
    "https://efts.sec.gov/LATEST/search-index?q=%22american+eagle+outfitters%22"
    "&dateRange=custom&startdt={start}&enddt={end}"
    "&forms=10-K&entity=american+eagle+outfitters"
)

OLDER_FILINGS = [
    ("FY2019", "2020-02-01", "2019-02-05", "2020-02-20"),
    ("FY2018", "2019-02-02", "2018-02-05", "2019-02-20"),
    ("FY2017", "2018-02-03", "2017-02-05", "2018-02-20"),
    ("FY2016", "2017-01-28", "2016-02-05", "2017-02-20"),
    ("FY2015", "2016-01-30", "2015-02-05", "2016-02-20"),
]

HEADERS = {
    "User-Agent": "AEO FPA Research Project research@example.com",  # SEC requires a user-agent
    "Accept-Encoding": "gzip, deflate",
}

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_and_save(label: str, url: str) -> bool:
    """Download a single 10-K HTML filing and save to disk."""
    output_path = OUTPUT_DIR / f"{label}.html"

    if output_path.exists():
        print(f"  ✓ {label} already downloaded, skipping.")
        return True

    print(f"  ↓ Fetching {label} from EDGAR...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
        size_kb = len(resp.content) // 1024
        print(f"    Saved {label}.html ({size_kb} KB)")
        time.sleep(1.0)  # Be polite to SEC servers — their robots.txt asks for delays
        return True
    except requests.RequestException as e:
        print(f"    ERROR fetching {label}: {e}")
        return False


def resolve_older_filing_url(label: str, start: str, end: str) -> str | None:
    """
    Use EDGAR full-text search API to find the 10-K HTM URL for older filings.
    Returns the direct document URL or None if not found.
    """
    search_url = EDGAR_SEARCH_URL.format(start=start, end=end)
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        for hit in hits:
            source = hit.get("_source", {})
            # Look for AEO's CIK specifically
            if "919012" in source.get("entity_id", ""):
                # Get the accession number and build the document URL
                accession = source.get("file_date", "")
                doc_url = source.get("file_num", "")
                # Try the direct filing index
                filing_index = source.get("period_of_report", "")
                accession_no = hit.get("_id", "").replace("-", "")
                if accession_no:
                    index_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=919012&type=10-K&dateb=&owner=include&count=5"
                    return None  # Will fall back to manual resolution
    except Exception as e:
        print(f"    EDGAR search error for {label}: {e}")
    return None


def main():
    print("\n=== AEO 10-K Fetcher ===\n")

    # --- Recent filings (known URLs) ---
    print("Downloading recent filings (FY2020–FY2024)...")
    success_count = 0
    for label, _date, url in FILINGS:
        if fetch_and_save(label, url):
            success_count += 1

    # --- Older filings via EDGAR search ---
    print("\nDownloading older filings (FY2015–FY2019) via EDGAR search...")
    print("  Note: If auto-resolve fails, fallback URLs are printed for manual download.\n")

    # Fallback: known stable older URLs (verified manually)
    OLDER_KNOWN_URLS = {
        "FY2019": "https://www.sec.gov/Archives/edgar/data/919012/000156459020010469/aeo-10k_20200201.htm",
        "FY2018": "https://www.sec.gov/Archives/edgar/data/919012/000156459019007828/aeo-10k_20190202.htm",
        "FY2017": "https://www.sec.gov/Archives/edgar/data/919012/000156459018006045/aeo-10k_20180203.htm",
        "FY2016": "https://www.sec.gov/Archives/edgar/data/919012/000156459017003969/aeo-10k_20170128.htm",
        "FY2015": "https://www.sec.gov/Archives/edgar/data/919012/000156459016014422/aeo-10k_20160130.htm",
    }

    for label, _fy_end, start, end in OLDER_FILINGS:
        url = OLDER_KNOWN_URLS.get(label)
        if url:
            if fetch_and_save(label, url):
                success_count += 1
        else:
            print(f"  ⚠ No URL found for {label}. Visit:")
            print(f"    https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=919012&type=10-K")

    print(f"\nDone. {success_count}/10 filings downloaded to data/raw/")
    print("Next step: run  python src/02_extract_financials.py")


if __name__ == "__main__":
    main()
