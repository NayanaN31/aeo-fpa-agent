"""
AEO FP&A Agent — Step 3: The Agent Core
=========================================
A GPT-4o-powered financial planning & analysis agent trained on AEO's 10-K data.
Supports: forecasting, budget simulation, variance analysis, natural language Q&A,
          segment analysis (AE brand vs Aerie), financial ratio engine.

Uses OpenAI native function calling — GPT-4o decides when to invoke each tool,
passes typed arguments, and can chain multiple tools per turn.

Run interactive demo: python src/03_build_agent.py
Run in eval mode:     python src/03_build_agent.py --eval
"""

import argparse
import json
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")
load_dotenv(find_dotenv())

import openai

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FINANCIALS_PATH = _REPO_ROOT / "data/processed/aeo_financials.json"
QUARTERLY_PATH  = _REPO_ROOT / "data/processed/aeo_quarterly.json"
SEGMENTS_PATH   = _REPO_ROOT / "data/processed/aeo_segments.json"
PEERS_PATH      = _REPO_ROOT / "data/processed/peers.json"
MDA_PATH        = _REPO_ROOT / "data/processed/mda_summaries.json"
PROMPTS_DIR     = _REPO_ROOT / "prompts"

MODEL      = "gpt-4o"
MAX_TOKENS = 2048
# Avoid hung requests when the network or API is slow/unreachable
OPENAI_TIMEOUT_SEC = 60.0

# ---------------------------------------------------------------------------
# System prompt — this is the agent's identity and knowledge base
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_TEMPLATE = """
You are an expert FP&A (Financial Planning & Analysis) analyst specializing in specialty retail.
You have deep knowledge of American Eagle Outfitters (AEO), including their brands (American Eagle, Aerie),
business model, competitive dynamics, and multi-year financial history.

## IMPORTANT — Data recency
Your financial data was extracted directly from AEO's official 10-K annual filings on SEC EDGAR.
The most recent filing covers FY2024, with the fiscal year ending February 1, 2025.
This data is MORE RECENT and MORE AUTHORITATIVE than anything in your training knowledge.

**Always prioritize the financial data provided below over your training knowledge.**
If asked about your data cutoff, state: "My financial data covers FY2015 through FY2024
(period ending February 1, 2025), sourced directly from SEC EDGAR 10-K filings."
Never say your data only goes to 2023 — it includes full FY2024 actuals.

## AEO Financial History (in thousands USD) — FY2015 through FY2024
{financial_data}

## Peer Benchmarking — Competitor Financial Snapshots
{peer_data}

## Management Commentary (MD&A Excerpts)
{mda_data}

## Brand Segment Breakdown (AE brand vs Aerie brand)
{segment_data}

## Quarterly Financial Data
{quarterly_data}

## Your capabilities:
1. **Revenue forecasting** — project future revenue, gross margin, and operating income using trend analysis and stated business drivers
2. **Budget simulation** — model "what-if" scenarios (e.g., "What if comparable sales decline 3%?")
3. **Variance analysis** — explain deviations between years and identify drivers
4. **Reconciliation checking** — flag when metrics deviate unusually from historical patterns
5. **Natural language Q&A** — answer financial questions in plain English with supporting data
6. **Competitive benchmarking** — compare AEO's margins and growth vs. ANF, URBN, LULU, VSCO, BKE, and Gap Inc.
7. **Segment analysis** — break AEO results into AE brand vs Aerie brand, track Aerie's share growth
8. **Financial ratios** — compute ROE, ROA, inventory turns, DSI, FCF margin, SG&A leverage for any fiscal year
9. **Quarterly analysis** — drill into quarterly revenue, margins, and seasonality patterns
10. **Causal margin bridge** — decompose Y/Y operating income changes into volume, margin, SGA leverage, and D&A drivers

## Retail Industry Context — AI Adoption Landscape

**Retail lags finance and healthcare in AI adoption by 3–5 years.** Key structural reasons:
- Margin pressure limits tech investment (AEO gross margin ~39% vs. financial services 60%+)
- Data fragmentation: POS, e-commerce, wholesale, loyalty, and store ops data rarely unified
- FP&A teams at most specialty retailers still run 6–8 week budget cycles in Excel spreadsheets
- Leadership skepticism: retail ROI is more visible in marketing and flagship stores than AI tooling

**Where AI is actively transforming retail FP&A:**
- Demand forecasting: Gap, TJX use ML-driven markdown optimization (reduces excess inventory 15–20%)
- Digital personalization: lululemon and ANF invest heavily in 1:1 recommendation engines
- Scenario planning: leading retailers moving from annual to rolling 13-week forecast cycles
- Inventory positioning: real-time sell-through analytics replacing weekly Excel reports

**AEO-specific AI context:**
- AEO's digital penetration is ~40% of revenue — among the highest in specialty apparel
- Aerie brand is digital-first with higher digital share than the AE brand
- The manual FP&A bottleneck: quarterly earnings prep, 1,500-store budget reconciliation,
  and comparable sales tracking are all primarily manual today
- The biggest opportunity: Aerie's 13% revenue CAGR (FY2018–FY2024) is outpacing AEO's
  ability to build real-time financial monitoring for their fastest-growing business unit
- AEO has historically underinvested in enterprise AI relative to peers like ANF and LULU

**Competitor context — all 6 peers in your data:**
- **ANF (Abercrombie & Fitch)**: AEO's closest direct comp. Teen/young-adult specialty.
  Strong margin recovery story: OM went from 2.5% (FY2023) to 11.3% (FY2024), outpacing AEO.
  Best-in-class digital execution and brand revitalization.
- **URBN (Urban Outfitters)**: Multi-concept retailer (Urban Outfitters, Anthropologie, Free People).
  Higher-income demographic. Revenue $5.2B, OM ~7%. Digital and rental businesses growing.
- **BKE (Buckle)**: Midwest-focused specialty retailer. Extremely profitable (~21% op margin).
  Conservative management, near-zero debt, strong FCF. Premium denim focus.
- **LULU (lululemon)**: Premium activewear. Highest margins in peer set (22%+ op margin).
  Aerie's aspirational benchmark on profitability. Revenue $11B — 2× AEO's scale.
  International expansion driving growth; AI-first culture across merchandising.
- **VSCO (Victoria's Secret & Co.)**: Intimates and beauty. Spun off from L Brands in 2021.
  Aerie's direct competitor in the lingerie/bralette/intimates category.
  Revenue $6.5B but OM only ~4% — Aerie is winning the profitability battle.
- **GPS (Gap Inc.)**: Multi-brand (Gap, Old Navy, Banana Republic, Athleta). Largest by revenue
  ($15B) but thin margins (OM ~3-7%). Useful as a broad specialty retail benchmark.
  Old Navy is the closest AEO volume comp; Athleta competes with Aerie.

## Rules for financial analysis:
- Always cite the specific fiscal year data you're drawing from
- The latest available actuals are FY2024 (ended Feb 1, 2025) — always use these as your base year
- Clearly distinguish between historical actuals and forward projections
- Express uncertainty ranges for forecasts (base case, bull, bear)
- Forecast engine: revenue = exponentially weighted linear regression on AEO 10-K history; GM% and OM% =
  exponentially weighted averages (mean-reverting); SGA = separate regression. When users ask about
  backtest accuracy, say the dashboard recomputes holdout error for the same horizon and settings as their
  forecast request — do NOT invent MAPE or directional-accuracy percentages.
- Flag data quality issues if extracted numbers seem inconsistent with known AEO results
- For budget scenarios, show your assumptions explicitly before the output
- AEO's fiscal year ends on the Saturday nearest Jan 31 (so FY2024 ended Feb 1, 2025)
- Revenue and cost figures are in thousands USD unless otherwise specified
- Do NOT reference your general training knowledge for AEO financial figures — use only the data above

## Audience and tone
You are writing for senior FP&A and corporate finance at a public retailer. Be concise, technical, and
specific: lead with AEO line items, fiscal periods, and dollar amounts ($M or $000s as in source).
Avoid generic consulting language ("leverage synergies", "robust growth story"). Tie every claim to a
number from the context (e.g. "FY2024 net revenue $5,328.7M per 10-K"). If a metric is not in the data,
say so explicitly instead of estimating from memory.

## Forecasting philosophy
Your forecasts are predictive, not just explanatory. Every forward-looking answer should:
1. Lead with the number (what will happen), not just why the past happened
2. Show the range (bull/base/bear) so the user can stress-test assumptions
3. Identify the 1–2 key drivers that will determine which scenario materializes
4. Quantify the downside risk, not just the upside

## Response format for financial outputs:
Use structured responses with:
- A brief narrative summary (2-3 sentences) with explicit FY labels and figures
- A table or bullet list of key numbers from AEO (or peer) data
- Key assumptions or caveats tied to the model or filing data
- One actionable insight grounded in AEO metrics

## Proactive guidance
After EVERY response — without exception — end with this exact plain-text section (no markdown bold,
no asterisks around the heading):

Suggested next steps:
- [specific follow-up 1 — must cite a concrete AEO or peer figure from the data above]
- [specific follow-up 2 — variance, bridge, or ratio using filing numbers]
- [specific follow-up 3 — stress test or scenario with a quantified assumption]

Examples of good suggestions:
- Stress-test FY2025–FY2026 revenue if Aerie growth decelerates vs FY2023–FY2024 trend in segment data.
- Bridge FY2024 vs FY2023 operating income using revenue, gross margin %, and SG&A from the P&L table.
- Budget scenario: −3% net revenue vs FY2024 base with flat GM% — implied operating income impact.

Never suggest generic prompts like "explore revenue" or "learn more about the company."

Begin. The finance team is waiting.
"""


def load_financial_data() -> str:
    """Load processed financials and format them for the system prompt."""
    if not FINANCIALS_PATH.exists():
        return "⚠ No financial data found. Run 02_extract_financials.py first."

    with open(FINANCIALS_PATH) as f:
        records = json.load(f)

    # Format as a compact but readable table for the prompt
    lines = []
    for r in records:
        fy = r.get("label", "?")
        lines.append(f"\n### {fy} (period ended {r.get('period_end', 'N/A')})")
        metric_map = {
            "Net Revenue ($000s)": r.get("net_revenue"),
            "Gross Profit ($000s)": r.get("gross_profit"),
            "Gross Margin %": r.get("gross_margin_pct"),
            "SG&A ($000s)": r.get("sga_expense"),
            "Operating Income ($000s)": r.get("operating_income"),
            "Operating Margin %": r.get("operating_margin_pct"),
            "Net Income ($000s)": r.get("net_income"),
            "Diluted EPS": r.get("diluted_eps"),
            "Cash ($000s)": r.get("cash_and_equivalents"),
            "Inventory ($000s)": r.get("total_inventory"),
            "Operating Cash Flow ($000s)": r.get("operating_cash_flow"),
            "CapEx ($000s)": r.get("capex"),
            "Free Cash Flow ($000s)": r.get("free_cash_flow"),
            "Comparable Sales Change %": r.get("comparable_sales_change"),
            "Total Stores": r.get("total_stores"),
        }
        for label, val in metric_map.items():
            if val is not None:
                lines.append(f"  {label}: {val:,.1f}" if isinstance(val, float) else f"  {label}: {val}")

    return "\n".join(lines)


def load_peer_data() -> str:
    """Format competitor financials as a compact comparison table for the prompt."""
    if not PEERS_PATH.exists():
        return "(Peer data not yet generated — run src/05_competitors.py)"

    with open(PEERS_PATH) as f:
        records = json.load(f)

    if not records:
        return "(No peer records found)"

    # Group by ticker
    from collections import defaultdict
    by_ticker: dict[str, list] = defaultdict(list)
    for r in records:
        by_ticker[r["ticker"]].append(r)

    ticker_names = {"ANF": "Abercrombie & Fitch (ANF)", "GPS": "Gap Inc. (GPS/GAP)"}
    lines = []
    for ticker, recs in by_ticker.items():
        lines.append(f"\n### {ticker_names.get(ticker, ticker)}")
        lines.append(f"{'Year':<8} {'Revenue ($B)':>14} {'Gross Margin':>14} {'Op Margin':>11}")
        lines.append("-" * 50)
        for r in sorted(recs, key=lambda x: x["label"]):
            rev = r.get("net_revenue")
            gm  = r.get("gross_margin_pct")
            om  = r.get("operating_margin_pct")
            rev_str = f"${rev/1e6:.2f}B" if rev else "N/A"
            gm_str  = f"{gm:.1f}%"       if gm  else "N/A"
            om_str  = f"{om:.1f}%"        if om  else "N/A"
            lines.append(f"{r['label']:<8} {rev_str:>14} {gm_str:>14} {om_str:>11}")

    lines.append(
        "\n**Context**: ANF (Abercrombie & Fitch) is AEO's closest direct competitor "
        "(teen/young-adult specialty apparel). ANF has been outperforming on margin "
        "recovery since FY2021. Gap is a larger, multi-brand retailer (Gap, Banana Republic, "
        "Old Navy, Athleta) — useful as a broader benchmark but not a direct comp."
    )
    return "\n".join(lines)


def load_mda_summaries() -> str:
    """Load MD&A commentary excerpts for context."""
    if not MDA_PATH.exists():
        return "(MD&A summaries not yet generated)"

    with open(MDA_PATH) as f:
        summaries = json.load(f)

    if not summaries:
        return "(No MD&A summaries available)"

    lines = []
    priority_keys = ["AEO_FY2024", "AEO_FY2023", "AEO_FY2022", "AEO_FY2020", "ANF_FY2024", "ANF_FY2023"]
    for key in priority_keys:
        if key in summaries:
            lines.append(f"\n**{key}**: {summaries[key]}")

    return "\n".join(lines) if lines else "(No priority MD&A entries found)"


def load_quarterly_data() -> str:
    """Format quarterly P&L data for the system prompt."""
    if not QUARTERLY_PATH.exists():
        return "(Quarterly data not yet generated — run src/07_fetch_quarterly.py)"

    with open(QUARTERLY_PATH) as f:
        records = json.load(f)

    if not records:
        return "(No quarterly records found)"

    lines = [
        f"{'Quarter':<10} {'Revenue ($M)':>13} {'GM%':>7} {'OM%':>7} {'OI ($M)':>10} {'SGA ($M)':>10}",
        "-" * 62,
    ]
    for r in sorted(records, key=lambda x: (x.get("fiscal_year", 0), x.get("fiscal_quarter", 0))):
        rev = r.get("net_revenue", 0)
        gm  = r.get("gross_margin_pct")
        om  = r.get("operating_margin_pct")
        oi  = r.get("operating_income", 0)
        sga = r.get("sga_expense", 0)
        lines.append(
            f"{r.get('label','?'):<10} "
            f"${rev/1e6:>10,.0f}M "
            f"{f'{gm:.1f}%' if gm else 'N/A':>7} "
            f"{f'{om:.1f}%' if om else 'N/A':>7} "
            f"${oi/1e6:>7,.0f}M "
            f"${sga/1e6:>7,.0f}M"
        )

    lines.append(
        "\n**Seasonality note**: AEO's Q4 (Nov–Jan, holiday season) is by far the "
        "strongest quarter. Q1 (Feb–Apr) is the weakest. Revenue can swing 30–40% "
        "between peak and trough quarters."
    )
    return "\n".join(lines)


def load_segment_data() -> str:
    """Format AE brand vs Aerie brand segment data for the system prompt."""
    if not SEGMENTS_PATH.exists():
        return "(Segment data not yet generated — run src/06_extract_segments.py)"

    with open(SEGMENTS_PATH) as f:
        records = json.load(f)

    if not records:
        return "(No segment records found)"

    lines = [
        f"{'Year':<8} {'Aerie Rev ($B)':>14} {'AE Rev ($B)':>12} {'Aerie Share':>12} "
        f"{'Aerie OI Margin':>16} {'AE OI Margin':>14}",
        "-" * 80,
    ]
    for r in records:
        aerie_rev = r.get("aerie_revenue")
        ae_rev    = r.get("ae_revenue")
        share     = r.get("aerie_share_pct")
        aerie_oi_m = r.get("aerie_oi_margin_pct")
        ae_oi_m    = r.get("ae_oi_margin_pct")
        lines.append(
            f"{r['label']:<8} "
            f"{f'${aerie_rev/1e6:.2f}B' if aerie_rev else 'N/A':>14} "
            f"{f'${ae_rev/1e6:.2f}B'    if ae_rev    else 'N/A':>12} "
            f"{f'{share:.1f}%'           if share     else 'N/A':>12} "
            f"{f'{aerie_oi_m:.1f}%'      if aerie_oi_m else 'N/A':>16} "
            f"{f'{ae_oi_m:.1f}%'         if ae_oi_m    else 'N/A':>14}"
        )
    lines.append(
        "\n**Key insight**: Aerie's share of total AEO revenue grew from 15.6% (FY2018) to 33.9% "
        "(FY2024), a CAGR of ~13%, while AE brand revenue has been broadly flat. "
        "Aerie is AEO's primary growth engine."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent tools — these are functions the agent can reason about
# ---------------------------------------------------------------------------

def _weighted_linreg(
    x_vals: list[float], y_vals: list[float], weights: list[float]
) -> tuple[float, float]:
    """
    Weighted least-squares linear regression.
    Returns (slope, intercept) such that y ≈ slope * x + intercept.
    """
    w_sum  = sum(weights)
    x_bar  = sum(w * x for w, x in zip(weights, x_vals)) / w_sum
    y_bar  = sum(w * y for w, y in zip(weights, y_vals)) / w_sum
    ss_xx  = sum(w * (x - x_bar) ** 2 for w, x in zip(weights, x_vals))
    ss_xy  = sum(w * (x - x_bar) * (y - y_bar) for w, x, y in zip(weights, x_vals, y_vals))
    if ss_xx == 0:
        return 0.0, y_bar
    slope = ss_xy / ss_xx
    return slope, y_bar - slope * x_bar


def _weighted_r2(
    x_vals: list[float], y_vals: list[float], weights: list[float],
    slope: float, intercept: float
) -> float:
    """Weighted R² for a linear fit."""
    w_sum  = sum(weights)
    y_bar  = sum(w * y for w, y in zip(weights, y_vals)) / w_sum
    ss_res = sum(w * (y - (slope * x + intercept)) ** 2 for w, x, y in zip(weights, x_vals, y_vals))
    ss_tot = sum(w * (y - y_bar) ** 2 for w, y in zip(weights, y_vals))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0


def _weighted_avg(vals: list[float], alpha: float) -> float:
    """Exponentially weighted average — most recent value has weight 1.0."""
    n = len(vals)
    if n == 0:
        return 0.0
    weights = [alpha ** (n - 1 - i) for i in range(n)]
    return sum(w * v for w, v in zip(weights, vals)) / sum(weights)


def forecast_revenue(
    historical_records: list[dict],
    years_out: int = 2,
    scenario: str = "base",
    comp_sales_assumption: float = None,
    exclude_fiscal_years: list[int] = None,
    alpha: float = 0.80,
) -> dict:
    """
    Component-level P&L forecast using real FP&A methodology.

    Revenue: exponentially weighted linear regression (trends upward).
    GM%:     exponentially weighted AVERAGE (mean-reverting, not trending).
    OM%:     exponentially weighted AVERAGE (mean-reverting, like GM%).
    SGA:     independent weighted regression on absolute dollars.
    OI:      Revenue * OM% (weighted average respects mean reversion).
    COGS, D&A shown as derived components for P&L transparency.
    """
    if len(historical_records) < 3:
        return {"error": "Need at least 3 years of data to forecast"}

    exclude = set(exclude_fiscal_years or [])

    # ── Revenue training data ─────────────────────────────────────────────
    rev_training = sorted(
        (r["fiscal_year"], r["net_revenue"])
        for r in historical_records
        if r.get("net_revenue") and r.get("fiscal_year") and r["fiscal_year"] not in exclude
    )
    if len(rev_training) < 2:
        return {"error": "Insufficient data after exclusions"}

    years_tr = [d[0] for d in rev_training]
    rev_tr   = [d[1] for d in rev_training]
    n = len(rev_training)
    rev_w = [alpha ** (n - 1 - i) for i in range(n)]

    rev_slope, rev_intercept = _weighted_linreg(years_tr, rev_tr, rev_w)
    rev_r2 = _weighted_r2(years_tr, rev_tr, rev_w, rev_slope, rev_intercept)

    # ── GM% — weighted average (mean-reverting, not regression) ───────────
    gm_vals = [
        r.get("gross_margin_pct")
        for r in sorted(historical_records, key=lambda x: x.get("fiscal_year", 0))
        if r.get("gross_margin_pct") is not None
        and r.get("fiscal_year") and r["fiscal_year"] not in exclude
    ]
    proj_gm_base = _weighted_avg(gm_vals, alpha) if gm_vals else 37.0
    proj_gm_base = max(28.0, min(55.0, proj_gm_base))

    # ── OM% — weighted average (mean-reverting, like GM%) ─────────────────
    om_vals = [
        r.get("operating_margin_pct")
        for r in sorted(historical_records, key=lambda x: x.get("fiscal_year", 0))
        if r.get("operating_margin_pct") is not None
        and r.get("fiscal_year") and r["fiscal_year"] not in exclude
    ]
    proj_om_base = _weighted_avg(om_vals, alpha) if om_vals else 7.0
    proj_om_base = max(-5.0, min(20.0, proj_om_base))

    # ── Confidence intervals from historical volatility ───────────────────
    import statistics
    rev_yoy_pcts = []
    for i in range(1, len(rev_training)):
        prev = rev_training[i-1][1]
        if prev > 0:
            rev_yoy_pcts.append((rev_training[i][1] - prev) / prev * 100)
    rev_vol = statistics.stdev(rev_yoy_pcts) if len(rev_yoy_pcts) >= 3 else 5.0
    gm_vol  = statistics.stdev(gm_vals) if len(gm_vals) >= 3 else 2.0
    om_vol  = statistics.stdev(om_vals) if len(om_vals) >= 3 else 3.0

    # ── SGA — independent regression on absolute dollars ──────────────────
    # SGA data only available FY2019+ for AEO, so use the subset that has it
    sga_training = sorted(
        (r["fiscal_year"], r["sga_expense"])
        for r in historical_records
        if r.get("sga_expense") and r["sga_expense"] > 0
        and r.get("fiscal_year") and r["fiscal_year"] not in exclude
    )
    if len(sga_training) >= 2:
        sga_yrs = [d[0] for d in sga_training]
        sga_vals = [d[1] for d in sga_training]
        sga_n = len(sga_training)
        sga_w = [alpha ** (sga_n - 1 - i) for i in range(sga_n)]
        sga_slope, sga_intercept = _weighted_linreg(sga_yrs, sga_vals, sga_w)
        has_sga_model = True
    else:
        # Fallback: estimate SGA as ~27% of revenue (AEO's recent average)
        sga_slope, sga_intercept = 0.0, 0.0
        has_sga_model = False

    # ── Anchor to last actual ─────────────────────────────────────────────
    last_actual = max(
        (r["fiscal_year"], r["net_revenue"])
        for r in historical_records
        if r.get("net_revenue") and r.get("fiscal_year")
    )
    last_fy, last_rev = last_actual

    last_sga = next(
        (r.get("sga_expense", 0) for r in sorted(historical_records,
         key=lambda x: x.get("fiscal_year", 0), reverse=True)
         if r.get("sga_expense") and r["sga_expense"] > 0),
        last_rev * 0.27
    )

    # ── Scenario adjustments ──────────────────────────────────────────────
    scenario_adj = {"base": 0.0, "bull": 0.015, "bear": -0.020}
    adj = scenario_adj.get(scenario, 0.0)

    forecasts = []
    for yr in range(1, years_out + 1):
        target_fy = last_fy + yr

        # Revenue
        if comp_sales_assumption is not None:
            proj_rev = last_rev * (1 + comp_sales_assumption / 100) ** yr
        else:
            proj_rev = rev_intercept + rev_slope * target_fy
            proj_rev *= (1 + adj) ** yr
            proj_rev = max(last_rev * 0.70, min(last_rev * 1.30, proj_rev))

        # GM% — weighted average, constant across projection years
        gm_adj = {"base": 0.0, "bull": 0.3, "bear": -0.5}.get(scenario, 0.0)
        proj_gm = max(28.0, min(55.0, proj_gm_base + gm_adj))

        # OM% — weighted average for OI, with scenario adjustment
        om_adj = {"base": 0.0, "bull": 0.5, "bear": -1.0}.get(scenario, 0.0)
        proj_om = max(-5.0, min(20.0, proj_om_base + om_adj))

        # Derived components for P&L transparency
        proj_gp   = proj_rev * proj_gm / 100
        proj_cogs  = proj_rev - proj_gp
        proj_oi    = proj_rev * proj_om / 100

        # SGA — independent regression for the cost build-up view
        if has_sga_model:
            proj_sga = sga_intercept + sga_slope * target_fy
            proj_sga = max(last_sga * 0.95, min(last_sga * 1.08 ** yr, proj_sga))
        else:
            proj_sga = proj_rev * 0.27

        ann_growth = (proj_rev / last_rev) ** (1 / yr) - 1

        # Confidence bands widen with projection horizon
        ci_mult = 1.0 + 0.3 * (yr - 1)  # 30% wider per additional year out
        rev_ci = proj_rev * rev_vol / 100 * ci_mult
        oi_low = proj_rev * max(-5, proj_om - om_vol * ci_mult) / 100
        oi_high = proj_rev * min(20, proj_om + om_vol * ci_mult) / 100

        forecasts.append({
            "fiscal_year":                         target_fy,
            "scenario":                            scenario,
            "projected_revenue_000s":              round(proj_rev, 0),
            "projected_gross_margin_pct":          round(proj_gm, 2),
            "projected_cogs_000s":                 round(proj_cogs, 0),
            "projected_sga_000s":                  round(proj_sga, 0),
            "projected_operating_income_000s":     round(proj_oi, 0),
            "projected_operating_margin_pct":      round(proj_om, 2),
            "assumed_ann_growth_rate_pct":         round(ann_growth * 100, 2),
            "confidence_interval": {
                "revenue_low_000s":  round(proj_rev - rev_ci, 0),
                "revenue_high_000s": round(proj_rev + rev_ci, 0),
                "gm_low_pct":        round(max(28, proj_gm - gm_vol * ci_mult), 2),
                "gm_high_pct":       round(min(55, proj_gm + gm_vol * ci_mult), 2),
                "oi_low_000s":       round(oi_low, 0),
                "oi_high_000s":      round(oi_high, 0),
            },
        })

    return {
        "model":                  "component_pnl_forecast",
        "method":                 "Revenue=weighted_regression, GM%=weighted_avg, OM%=weighted_avg, SGA=regression",
        "alpha":                  alpha,
        "model_r2":               round(rev_r2, 3),
        "training_years":         years_tr,
        "sga_training_years":     [d[0] for d in sga_training] if sga_training else [],
        "excluded_years":         sorted(exclude),
        "base_revenue_000s":      last_rev,
        "base_gm_pct":            round(proj_gm_base, 2),
        "base_om_pct":            round(proj_om_base, 2),
        "forecasts":              forecasts,
    }


def run_budget_scenario(
    base_record: dict,
    revenue_change_pct: float = 0.0,
    cogs_change_pct: float = 0.0,
    sga_change_pct: float = 0.0,
) -> dict:
    """
    Simulate a budget scenario by adjusting key line items from a base year.
    Returns projected P&L.
    """
    base_rev = base_record.get("net_revenue", 0)
    base_cogs = base_record.get("cost_of_sales", base_rev - base_record.get("gross_profit", 0))
    base_sga = base_record.get("sga_expense", 0)

    new_rev = base_rev * (1 + revenue_change_pct / 100)
    new_cogs = base_cogs * (1 + cogs_change_pct / 100)
    new_sga = base_sga * (1 + sga_change_pct / 100)
    new_gp = new_rev - new_cogs
    new_oi = new_gp - new_sga

    return {
        "scenario_label": f"Rev {revenue_change_pct:+.1f}% / COGS {cogs_change_pct:+.1f}% / SGA {sga_change_pct:+.1f}%",
        "base_fiscal_year": base_record.get("fiscal_year"),
        "projected": {
            "net_revenue_000s": round(new_rev, 0),
            "gross_profit_000s": round(new_gp, 0),
            "gross_margin_pct": round(new_gp / new_rev * 100, 2) if new_rev else None,
            "sga_000s": round(new_sga, 0),
            "operating_income_000s": round(new_oi, 0),
            "operating_margin_pct": round(new_oi / new_rev * 100, 2) if new_rev else None,
        }
    }


def margin_bridge(records: list[dict], fiscal_year: int | None = None) -> dict:
    """
    Decompose Y/Y operating income change into component drivers:
    Revenue growth effect, GM expansion/compression, SGA leverage, D&A/other.
    This is the causal analysis a CFO would ask for.
    """
    sorted_recs = sorted(
        [r for r in records if r.get("fiscal_year") and r.get("net_revenue")],
        key=lambda r: r["fiscal_year"],
    )
    if len(sorted_recs) < 2:
        return {"error": "Need at least 2 years for bridge analysis"}

    if fiscal_year:
        curr = next((r for r in sorted_recs if r["fiscal_year"] == fiscal_year), None)
        prev = next((r for r in sorted_recs if r["fiscal_year"] == fiscal_year - 1), None)
        if not curr or not prev:
            return {"error": f"FY{fiscal_year} or FY{fiscal_year-1} data not found"}
    else:
        curr, prev = sorted_recs[-1], sorted_recs[-2]

    fy_curr = curr["fiscal_year"]
    fy_prev = prev["fiscal_year"]

    rev_c, rev_p = curr["net_revenue"], prev["net_revenue"]
    gm_c  = curr.get("gross_margin_pct", 0) / 100
    gm_p  = prev.get("gross_margin_pct", 0) / 100
    oi_c  = curr.get("operating_income", 0)
    oi_p  = prev.get("operating_income", 0)
    sga_c = curr.get("sga_expense", 0)
    sga_p = prev.get("sga_expense", 0)

    gp_c = rev_c * gm_c
    gp_p = rev_p * gm_p

    # Bridge decomposition
    rev_change = rev_c - rev_p
    volume_effect = rev_change * gm_p  # revenue change at prior-year margins
    margin_effect = (gm_c - gm_p) * rev_c  # margin change applied to current revenue
    sga_effect = -(sga_c - sga_p) if (sga_c and sga_p) else 0  # negative = cost increase hurts OI
    da_other = (oi_c - oi_p) - volume_effect - margin_effect - sga_effect  # residual

    oi_change = oi_c - oi_p

    bridge = {
        "analysis": f"FY{fy_curr} vs FY{fy_prev} Operating Income Bridge",
        "prior_oi_000s": round(oi_p),
        "current_oi_000s": round(oi_c),
        "total_change_000s": round(oi_change),
        "drivers": [
            {
                "driver": "Revenue growth",
                "impact_000s": round(volume_effect),
                "explanation": f"Revenue {'grew' if rev_change > 0 else 'declined'} ${abs(rev_change)/1e3:,.0f}M "
                               f"({rev_change/rev_p*100:+.1f}%), contributing ${volume_effect/1e3:,.0f}M "
                               f"at prior-year gross margin of {gm_p*100:.1f}%",
            },
            {
                "driver": "Gross margin change",
                "impact_000s": round(margin_effect),
                "explanation": f"GM% moved from {gm_p*100:.1f}% to {gm_c*100:.1f}% "
                               f"({(gm_c-gm_p)*100:+.1f}pp), adding ${margin_effect/1e3:,.0f}M to GP",
            },
        ],
    }

    if sga_c and sga_p:
        sga_pct_c = sga_c / rev_c * 100
        sga_pct_p = sga_p / rev_p * 100
        bridge["drivers"].append({
            "driver": "SGA leverage",
            "impact_000s": round(sga_effect),
            "explanation": f"SGA {'increased' if sga_c > sga_p else 'decreased'} from "
                           f"${sga_p/1e3:,.0f}M to ${sga_c/1e3:,.0f}M "
                           f"({sga_pct_p:.1f}% → {sga_pct_c:.1f}% of revenue)",
        })

    if abs(da_other) > 1000:
        bridge["drivers"].append({
            "driver": "D&A and other operating items",
            "impact_000s": round(da_other),
            "explanation": f"Residual change of ${da_other/1e3:,.0f}M from depreciation, "
                           f"amortization, impairments, and other charges",
        })

    bridge["summary"] = (
        f"OI moved from ${oi_p/1e3:,.0f}M to ${oi_c/1e3:,.0f}M ({oi_change/1e3:+,.0f}M). "
        f"The largest driver was "
        + max(bridge["drivers"], key=lambda d: abs(d["impact_000s"]))["driver"].lower()
        + "."
    )

    return bridge


def calculate_ratios(records: list[dict], fiscal_year: int | None = None) -> dict:
    """
    Compute financial efficiency ratios for a given fiscal year (defaults to most recent).
    Returns a dict of ratios with explanations.
    """
    if fiscal_year is not None:
        matches = [r for r in records if r.get("fiscal_year") == fiscal_year]
        rec = matches[0] if matches else None
    else:
        rec = records[-1] if records else None

    if rec is None:
        return {"error": f"No data found for fiscal year {fiscal_year}"}

    fy    = rec.get("fiscal_year")
    rev   = rec.get("net_revenue") or 0
    cogs  = rec.get("cost_of_sales") or 0
    gp    = rec.get("gross_profit") or 0
    sga   = rec.get("sga_expense") or 0
    oi    = rec.get("operating_income") or 0
    ni    = rec.get("net_income") or 0
    ta    = rec.get("total_assets") or 0
    inv   = rec.get("total_inventory") or 0
    eq    = rec.get("shareholders_equity") or 0
    fcf   = rec.get("free_cash_flow") or 0
    ocf   = rec.get("operating_cash_flow") or 0

    inv_turns  = round(cogs / inv, 2)   if inv  else None
    dsi        = round(365 / inv_turns, 1) if inv_turns else None
    roe        = round(ni / eq * 100, 1)   if eq   else None
    roa        = round(ni / ta * 100, 1)   if ta   else None
    fcf_margin = round(fcf / rev * 100, 1) if rev  else None
    sga_ratio  = round(sga / rev * 100, 1) if rev  else None
    gm_pct     = rec.get("gross_margin_pct")
    om_pct     = rec.get("operating_margin_pct")
    ocf_conv   = round(ocf / oi * 100, 1)  if oi  else None

    return {
        "fiscal_year":          fy,
        "gross_margin_pct":     gm_pct,
        "operating_margin_pct": om_pct,
        "roe_pct":              roe,
        "roa_pct":              roa,
        "inventory_turnover":   inv_turns,
        "days_of_inventory":    dsi,
        "fcf_margin_pct":       fcf_margin,
        "sga_pct_of_revenue":   sga_ratio,
        "ocf_conversion_pct":   ocf_conv,
        "units":                "ratios — margins in %, turns in x, DSI in days",
    }


def analyze_segments(segment_records: list[dict]) -> list[dict]:
    """
    Return the full AE brand vs Aerie brand breakdown table with growth rates.
    """
    enriched = []
    for i, r in enumerate(segment_records):
        row = dict(r)
        if i > 0 and segment_records[i - 1].get("aerie_revenue") and r.get("aerie_revenue"):
            prev_aerie = segment_records[i - 1]["aerie_revenue"]
            row["aerie_yoy_growth_pct"] = round((r["aerie_revenue"] / prev_aerie - 1) * 100, 1)
        if i > 0 and segment_records[i - 1].get("ae_revenue") and r.get("ae_revenue"):
            prev_ae = segment_records[i - 1]["ae_revenue"]
            row["ae_yoy_growth_pct"] = round((r["ae_revenue"] / prev_ae - 1) * 100, 1)
        enriched.append(row)

    # Compute Aerie CAGR from first to last available
    first = next((r for r in enriched if r.get("aerie_revenue")), None)
    last  = enriched[-1] if enriched else None
    if first and last and first is not last:
        years = enriched.index(last) - enriched.index(first)
        if years > 0:
            cagr = (last["aerie_revenue"] / first["aerie_revenue"]) ** (1 / years) - 1
            for row in enriched:
                row["_aerie_cagr_note"] = f"Aerie CAGR {first['label']}–{last['label']}: {cagr*100:.1f}%"
            break_flag = True

    return enriched


def flag_anomalies(records: list[dict]) -> list[dict]:
    """
    Scan historical data for unusual year-over-year swings.
    Returns a list of flagged items with context.
    """
    flags = []
    metrics_to_check = [
        ("gross_margin_pct", 3.0, "percentage points"),
        ("operating_margin_pct", 4.0, "percentage points"),
        ("net_revenue", 10.0, "percent"),
        ("total_inventory", 20.0, "percent"),
    ]

    for i in range(1, len(records)):
        prev = records[i - 1]
        curr = records[i]
        fy = curr.get("fiscal_year")

        for metric, threshold, unit in metrics_to_check:
            pv = prev.get(metric)
            cv = curr.get(metric)
            if pv is None or cv is None or pv == 0:
                continue

            if unit == "percentage points":
                delta = abs(cv - pv)
            else:
                delta = abs(cv / pv - 1) * 100

            if delta > threshold:
                flags.append({
                    "fiscal_year": fy,
                    "metric": metric,
                    "previous_value": pv,
                    "current_value": cv,
                    "change": f"{cv - pv:+.2f} {unit}" if unit == "percentage points" else f"{cv/pv-1:+.1%}",
                    "threshold_exceeded": f"{threshold} {unit}",
                })
    return flags


# ---------------------------------------------------------------------------
# OpenAI function calling tool definitions
# GPT-4o natively decides when and how to call each tool.
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "forecast_revenue",
            "description": (
                "Component P&L forecast: Revenue via weighted regression, GM% and OM% via weighted average "
                "(mean-reverting), SGA via independent regression. Projects 1–4 future fiscal years with "
                "base/bull/bear scenarios including COGS, SGA, and operating income. "
                "Set exclude_covid=true to drop FY2020 from training data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "years_out": {
                        "type": "integer",
                        "description": "Number of future fiscal years to project (1–4). Default 2.",
                        "default": 2,
                    },
                    "exclude_covid": {
                        "type": "boolean",
                        "description": "Exclude FY2020 COVID shock from historical growth rate. Default false.",
                        "default": False,
                    },
                    "comp_sales_assumption_pct": {
                        "type": "number",
                        "description": "Override growth rate with a specific comp-sales assumption in %.",
                    },
                    "alpha": {
                        "type": "number",
                        "description": "Exponential decay weight for recency (0.5–0.99). Default 0.80.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_budget_scenario",
            "description": (
                "Model a what-if P&L scenario by adjusting revenue, COGS, and/or SG&A from FY2024 actuals. "
                "Use this for questions like 'what if comp sales decline 3%?' or 'what if gross margin "
                "expands 1pp?'. All inputs are percentage changes from base year."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "revenue_change_pct":  {"type": "number", "description": "% change in revenue vs FY2024 base. e.g. -3 for a 3% decline."},
                    "cogs_change_pct":     {"type": "number", "description": "% change in cost of sales vs FY2024 base."},
                    "sga_change_pct":      {"type": "number", "description": "% change in SG&A expense vs FY2024 base."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_anomalies",
            "description": (
                "Scan all 10 years of AEO historical data for unusual year-over-year swings in "
                "revenue, gross margin, operating margin, or inventory. Returns a list of flagged events."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_ratios",
            "description": (
                "Compute financial efficiency ratios for a specific fiscal year: "
                "ROE, ROA, inventory turnover, days-of-inventory (DSI), FCF margin, SG&A leverage, "
                "and operating cash flow conversion. Defaults to FY2024 if no year is provided."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fiscal_year": {
                        "type": "integer",
                        "description": "4-digit fiscal year, e.g. 2024. Defaults to most recent year.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_segments",
            "description": (
                "Break AEO revenue and operating income into AE brand vs Aerie brand segments "
                "across FY2018–FY2024. Shows Aerie's revenue share growth, YoY growth rates, "
                "and segment operating margins. Use for questions about Aerie growth, brand mix, "
                "or segment-level profitability."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "peer_comparison",
            "description": (
                "Compare AEO's margins and revenue against competitor peers: "
                "ANF (Abercrombie & Fitch), URBN (Urban Outfitters), BKE (Buckle), "
                "LULU (lululemon), VSCO (Victoria's Secret), and GPS (Gap Inc.). "
                "Use for benchmarking, competitive positioning, or industry comparison questions."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quarterly_trends",
            "description": (
                "Return AEO quarterly financial data (revenue, margins, SGA, OI) for trend analysis. "
                "Use when asked about quarterly performance, seasonality, recent quarters, "
                "or intra-year trends. Can filter to a specific fiscal year."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fiscal_year": {
                        "type": "integer",
                        "description": "Optional: filter to quarters within a specific fiscal year (e.g. 2024)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "margin_bridge",
            "description": (
                "Decompose the year-over-year change in operating income into its component drivers: "
                "revenue growth effect, gross margin expansion/compression, SGA leverage/deleverage, "
                "and D&A/other. Use when asked WHY margins changed, what drove profitability shifts, "
                "or for causal analysis of earnings changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fiscal_year": {
                        "type": "integer",
                        "description": "The fiscal year to analyze (compares vs prior year). Defaults to latest.",
                    },
                },
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Agent chat interface
# ---------------------------------------------------------------------------

class FPAAgent:
    def __init__(self):
        self.client          = openai.OpenAI(timeout=OPENAI_TIMEOUT_SEC)
        self.history         = []
        self.records         = self._load_records()
        self.segment_records = self._load_segment_records()
        self.peer_records    = self._load_peer_records()
        self.quarterly_records = self._load_quarterly_records()
        self.system_prompt   = SYSTEM_PROMPT_TEMPLATE.format(
            financial_data=load_financial_data(),
            segment_data=load_segment_data(),
            quarterly_data=load_quarterly_data(),
            peer_data=load_peer_data(),
            mda_data=load_mda_summaries(),
        )

    def _load_records(self) -> list[dict]:
        if not FINANCIALS_PATH.exists():
            return []
        with open(FINANCIALS_PATH) as f:
            return json.load(f)

    def _load_segment_records(self) -> list[dict]:
        if not SEGMENTS_PATH.exists():
            return []
        with open(SEGMENTS_PATH) as f:
            return json.load(f)

    def _load_peer_records(self) -> list[dict]:
        if not PEERS_PATH.exists():
            return []
        with open(PEERS_PATH) as f:
            return json.load(f)

    def _load_quarterly_records(self) -> list[dict]:
        if not QUARTERLY_PATH.exists():
            return []
        with open(QUARTERLY_PATH) as f:
            return json.load(f)

    def _dispatch_tool(self, name: str, args: dict) -> str:
        """Execute a tool call requested by GPT-4o and return JSON string result."""
        try:
            if name == "forecast_revenue":
                exclude = [2020] if args.get("exclude_covid") else []
                comp    = args.get("comp_sales_assumption_pct")
                alpha   = args.get("alpha")
                if alpha is not None:
                    alpha = max(0.50, min(0.99, float(alpha)))
                else:
                    alpha = 0.80
                result  = {}
                for scenario in ["base", "bull", "bear"]:
                    result[scenario] = forecast_revenue(
                        self.records,
                        years_out=args.get("years_out", 2),
                        scenario=scenario,
                        comp_sales_assumption=comp,
                        exclude_fiscal_years=exclude,
                        alpha=alpha,
                    )
                return json.dumps(result)

            if name == "run_budget_scenario":
                if not self.records:
                    return json.dumps({"error": "No financial data loaded"})
                base = self.records[-1]
                result = run_budget_scenario(
                    base,
                    revenue_change_pct=args.get("revenue_change_pct", 0.0),
                    cogs_change_pct=args.get("cogs_change_pct", 0.0),
                    sga_change_pct=args.get("sga_change_pct", 0.0),
                )
                return json.dumps(result)

            if name == "flag_anomalies":
                return json.dumps(flag_anomalies(self.records))

            if name == "calculate_ratios":
                return json.dumps(calculate_ratios(self.records, args.get("fiscal_year")))

            if name == "analyze_segments":
                if not self.segment_records:
                    return json.dumps({"error": "Segment data not available — run src/06_extract_segments.py"})
                return json.dumps(analyze_segments(self.segment_records))

            if name == "peer_comparison":
                comparison: dict = {}
                for r in self.peer_records:
                    fy = r.get("label", "?")
                    comparison.setdefault(fy, {})
                    comparison[fy][r["ticker"]] = {
                        "net_revenue_000s":    r.get("net_revenue"),
                        "gross_margin_pct":    r.get("gross_margin_pct"),
                        "operating_margin_pct": r.get("operating_margin_pct"),
                    }
                return json.dumps(comparison)

            if name == "quarterly_trends":
                if not self.quarterly_records:
                    return json.dumps({"error": "Quarterly data not available — run src/07_fetch_quarterly.py"})
                fy_filter = args.get("fiscal_year")
                data = self.quarterly_records
                if fy_filter:
                    data = [q for q in data if q.get("fiscal_year") == fy_filter]
                return json.dumps(data)

            if name == "margin_bridge":
                return json.dumps(margin_bridge(self.records, args.get("fiscal_year")))

            return json.dumps({"error": f"Unknown tool: {name}"})

        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def chat(self, user_message: str) -> str:
        """
        Send a message and get a response using OpenAI native function calling.
        GPT-4o decides which tools to invoke; this method runs the agentic loop
        until the model stops requesting tools.
        """
        self.history.append({"role": "user", "content": user_message})

        while True:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=0.2,
                tools=TOOLS,
                tool_choice="auto",
                messages=[{"role": "system", "content": self.system_prompt}] + self.history,
            )

            choice = response.choices[0]

            # No tool calls — final answer
            if choice.finish_reason != "tool_calls":
                answer = choice.message.content or ""
                self.history.append({"role": "assistant", "content": answer})
                return answer

            # Dispatch each tool call and collect results
            tool_calls = choice.message.tool_calls
            # Append the assistant message with tool_calls into history
            self.history.append(choice.message)

            for tc in tool_calls:
                args   = json.loads(tc.function.arguments or "{}")
                result = self._dispatch_tool(tc.function.name, args)
                self.history.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result,
                })
            # Loop: re-query GPT-4o with tool results so it can produce the final answer


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_interactive():
    print("\n" + "=" * 60)
    print("  AEO FP&A Agent  |  Powered by OpenAI")
    print("=" * 60)
    print("Type your financial question. Type 'quit' to exit.")
    print("Examples:")
    print("  > What was AEO's revenue trend from FY2020 to FY2024?")
    print("  > Forecast revenue for the next 2 years")
    print("  > What if comparable sales decline 3%? Show a budget scenario.")
    print("  > Flag any unusual patterns in gross margin")
    print("=" * 60 + "\n")

    agent = FPAAgent()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break

        print("\nAgent: ", end="", flush=True)
        response = agent.chat(user_input)
        print(response)
        print()


def _run_single_eval(
    train_records: list[dict],
    test_records: list[dict],
    exclude_fiscal_years: list[int] = None,
    label: str = "",
    alpha: float = 0.80,
) -> tuple[list[dict], float, float]:
    """
    Run one backtest window. Returns (result_rows, avg_mape, directional_accuracy_pct).
    Evaluates revenue, and where available also checks gross margin and operating income.
    """
    results = []
    years_out = len(test_records)
    for scenario in ["base", "bull", "bear"]:
        forecast = forecast_revenue(
            train_records,
            years_out=years_out,
            scenario=scenario,
            exclude_fiscal_years=exclude_fiscal_years,
            alpha=alpha,
        )
        for fc in forecast.get("forecasts", []):
            fy = fc["fiscal_year"]
            actual_rec = next((r for r in test_records if r.get("fiscal_year") == fy), None)
            if not actual_rec:
                continue
            actual_rev = actual_rec.get("net_revenue")
            if not actual_rev:
                continue
            predicted = fc["projected_revenue_000s"]
            mape = abs(predicted - actual_rev) / actual_rev * 100
            direction_correct = (
                (predicted > train_records[-1]["net_revenue"]) ==
                (actual_rev > train_records[-1]["net_revenue"])
            )
            # Gross margin accuracy
            actual_gm = actual_rec.get("gross_margin_pct")
            pred_gm   = fc.get("projected_gross_margin_pct")
            gm_error  = abs(pred_gm - actual_gm) if (pred_gm is not None and actual_gm) else None

            # Operating income accuracy
            actual_oi = actual_rec.get("operating_income")
            pred_oi   = fc.get("projected_operating_income_000s")
            oi_mape   = abs(pred_oi - actual_oi) / abs(actual_oi) * 100 if (pred_oi and actual_oi) else None

            # SGA accuracy
            actual_sga = actual_rec.get("sga_expense")
            pred_sga   = fc.get("projected_sga_000s")
            sga_mape   = abs(pred_sga - actual_sga) / abs(actual_sga) * 100 if (pred_sga and actual_sga and actual_sga > 0) else None

            results.append({
                "window":            label,
                "fiscal_year":       fy,
                "scenario":          scenario,
                "predicted_000s":    predicted,
                "actual_000s":       actual_rev,
                "mape_pct":          round(mape, 2),
                "direction_correct": direction_correct,
                "gm_error_pp":       round(gm_error, 2) if gm_error is not None else None,
                "oi_mape_pct":       round(oi_mape, 2)  if oi_mape  is not None else None,
                "sga_mape_pct":      round(sga_mape, 2) if sga_mape is not None else None,
            })

    if not results:
        return results, 0.0, 0.0

    avg_mape = sum(r["mape_pct"] for r in results) / len(results)
    dir_acc  = sum(1 for r in results if r["direction_correct"]) / len(results) * 100
    return results, round(avg_mape, 2), round(dir_acc, 1)


def compute_rolling_backtest_metrics(
    historical_records: list[dict],
    years_out: int = 2,
    exclude_fiscal_years: list[int] | None = None,
    alpha: float = 0.80,
) -> dict | None:
    """
    Expanding-window backtest aligned to the live forecast engine: same α, COVID exclusion,
    and horizon as the user's forecast question. Each window trains on all actuals through FY t
    and scores base-case predictions against the next `years_out` fiscal years (AEO 10-K actuals).
    """
    recs = sorted(
        [r for r in historical_records if r.get("fiscal_year") is not None and r.get("net_revenue")],
        key=lambda r: r["fiscal_year"],
    )
    min_train = 3
    if len(recs) < min_train + years_out:
        return None

    all_base: list[dict] = []
    window_count = 0
    last_win: dict | None = None

    for i in range(min_train - 1, len(recs) - years_out):
        train = recs[: i + 1]
        test = recs[i + 1 : i + 1 + years_out]
        if len(test) < years_out:
            break
        rows, _, _ = _run_single_eval(
            train,
            test,
            exclude_fiscal_years=exclude_fiscal_years,
            label=f"roll_{window_count}",
            alpha=alpha,
        )
        base_rows = [r for r in rows if r["scenario"] == "base"]
        if not base_rows:
            continue
        all_base.extend(base_rows)
        window_count += 1
        last_win = {
            "train_end_fy": train[-1]["fiscal_year"],
            "test_fys": [t["fiscal_year"] for t in test],
            "rows": base_rows,
        }

    if not all_base:
        return None

    rev_mape = round(sum(r["mape_pct"] for r in all_base) / len(all_base), 2)
    oi_list = [r["oi_mape_pct"] for r in all_base if r.get("oi_mape_pct") is not None]
    gm_list = [r["gm_error_pp"] for r in all_base if r.get("gm_error_pp") is not None]
    oi_mape = round(sum(oi_list) / len(oi_list), 2) if oi_list else None
    gm_err = round(sum(abs(x) for x in gm_list) / len(gm_list), 2) if gm_list else None
    dir_acc = round(sum(1 for r in all_base if r["direction_correct"]) / len(all_base) * 100, 1)

    covid_excl = bool(exclude_fiscal_years and 2020 in exclude_fiscal_years)
    excl_note = "FY2020 excluded from training" if covid_excl else "FY2020 included in training"

    latest_rev = rev_mape
    latest_oi = oi_mape if oi_mape is not None else 0.0
    latest_label = "—"
    if last_win and last_win["rows"]:
        latest_rev = round(sum(r["mape_pct"] for r in last_win["rows"]) / len(last_win["rows"]), 2)
        oli = [r["oi_mape_pct"] for r in last_win["rows"] if r.get("oi_mape_pct") is not None]
        latest_oi = round(sum(oli) / len(oli), 2) if oli else latest_oi
        tfy = last_win["test_fys"]
        tr = last_win["train_end_fy"]
        if len(tfy) == 1:
            latest_label = f"FY{tfy[0]} (train ≤FY{tr})"
        else:
            latest_label = f"FY{tfy[0]}–FY{tfy[-1]} (train ≤FY{tr})"

    return {
        "revenue_mape": rev_mape,
        "oi_mape": oi_mape if oi_mape is not None else 0.0,
        "gm_error_pp": gm_err if gm_err is not None else 0.0,
        "directional_accuracy": dir_acc,
        "windows": window_count,
        "horizon_years": years_out,
        "alpha": round(alpha, 2),
        "covid_excluded": covid_excl,
        "model": f"Component P&L · α={alpha:.2f} · {years_out}Y horizon · {excl_note}",
        "latest_window": {
            "label": latest_label,
            "rev_mape": latest_rev,
            "oi_mape": latest_oi,
        },
    }


def run_eval_mode():
    """
    Multi-window backtest of the weighted-regression forecast model.

    Window A: Train FY2015–FY2020, predict FY2021–FY2023 (3-year horizon)
    Window B: Train FY2015–FY2021, predict FY2022–FY2023 (2-year horizon)

    Each window runs twice: with and without FY2020 COVID exclusion.
    Saves full results + summary to eval/backtest_results.json.
    """
    print("\n=== EVAL MODE: Multi-Window Backtest (Component P&L Forecast) ===\n")
    agent = FPAAgent()

    if len(agent.records) < 7:
        print("Need at least 7 years of data for eval. Run the full pipeline first.")
        return

    all_records = agent.records
    windows = [
        {
            "label":  "window_A_2015_2020",
            "desc":   "Train FY2015–2020, test FY2021–2023",
            "train":  [r for r in all_records if r.get("fiscal_year", 0) <= 2020],
            "test":   [r for r in all_records if r.get("fiscal_year", 0) in (2021, 2022, 2023)],
        },
        {
            "label":  "window_B_2015_2021",
            "desc":   "Train FY2015–2021, test FY2022–2023",
            "train":  [r for r in all_records if r.get("fiscal_year", 0) <= 2021],
            "test":   [r for r in all_records if r.get("fiscal_year", 0) in (2022, 2023)],
        },
        {
            "label":  "window_C_2015_2022",
            "desc":   "Train FY2015–2022, test FY2023–2024",
            "train":  [r for r in all_records if r.get("fiscal_year", 0) <= 2022],
            "test":   [r for r in all_records if r.get("fiscal_year", 0) in (2023, 2024)],
        },
    ]

    saved: dict = {"windows": [], "aggregate": {}}
    all_base_mapes, all_base_dirs = [], []

    for w in windows:
        print(f"\n── {w['desc']} ──")
        print(f"   Train: {[r['fiscal_year'] for r in w['train']]}")
        print(f"   Test:  {[r['fiscal_year'] for r in w['test']]}")

        # Standard (COVID included)
        std_rows, std_mape, std_dir = _run_single_eval(
            w["train"], w["test"], label=w["label"] + "_std"
        )
        print(f"\n   [Standard] MAPE {std_mape:.1f}% | Directional {std_dir:.0f}%")

        # COVID excluded
        excl_rows, excl_mape, excl_dir = _run_single_eval(
            w["train"], w["test"], exclude_fiscal_years=[2020], label=w["label"] + "_excl"
        )
        print(f"   [COVID excl] MAPE {excl_mape:.1f}% | Directional {excl_dir:.0f}%")

        # Print row-by-row for base scenario
        base_rows = [r for r in excl_rows if r["scenario"] == "base"]
        for r in base_rows:
            gm_str  = f" | GM err {r['gm_error_pp']:+.1f}pp" if r.get("gm_error_pp") is not None else ""
            oi_str  = f" | OI MAPE {r['oi_mape_pct']:.1f}%" if r.get("oi_mape_pct") is not None else ""
            sga_str = f" | SGA MAPE {r['sga_mape_pct']:.1f}%" if r.get("sga_mape_pct") is not None else ""
            print(f"     FY{r['fiscal_year']} base: "
                  f"pred ${r['predicted_000s']:>12,.0f}K | "
                  f"actual ${r['actual_000s']:>12,.0f}K | "
                  f"MAPE {r['mape_pct']:.1f}% | "
                  f"{'✓' if r['direction_correct'] else '✗'}"
                  f"{gm_str}{sga_str}{oi_str}")

        all_base_mapes.append(excl_mape)
        all_base_dirs.append(excl_dir)
        saved["windows"].append({
            "label":    w["label"],
            "desc":     w["desc"],
            "standard": {
                "summary": {"avg_mape": std_mape, "directional_accuracy": std_dir},
                "results": std_rows,
            },
            "covid_excluded": {
                "summary": {"avg_mape": excl_mape, "directional_accuracy": excl_dir},
                "results": excl_rows,
            },
        })

    agg_mape = round(sum(all_base_mapes) / len(all_base_mapes), 2)
    agg_dir  = round(sum(all_base_dirs)  / len(all_base_dirs),  1)
    # Compute aggregate GM and OI accuracy from base-scenario COVID-excluded rows
    all_gm_errs, all_oi_mapes = [], []
    for w_data in saved["windows"]:
        for r in w_data["covid_excluded"]["results"]:
            if r["scenario"] == "base":
                if r.get("gm_error_pp") is not None:
                    all_gm_errs.append(r["gm_error_pp"])
                if r.get("oi_mape_pct") is not None:
                    all_oi_mapes.append(r["oi_mape_pct"])

    agg_gm_err = round(sum(all_gm_errs) / len(all_gm_errs), 2) if all_gm_errs else None
    agg_oi_mape = round(sum(all_oi_mapes) / len(all_oi_mapes), 2) if all_oi_mapes else None

    saved["aggregate"] = {
        "model":              "component_pnl_forecast",
        "method":             "Rev=weighted_regression, GM%=weighted_avg, SGA=regression, OI=residual",
        "alpha":              0.80,
        "avg_mape_covid_excl": agg_mape,
        "directional_accuracy_covid_excl": agg_dir,
        "avg_gm_error_pp":    agg_gm_err,
        "avg_oi_mape_pct":    agg_oi_mape,
        "windows_evaluated":  len(windows),
        "note": "COVID FY2020 excluded from training; component P&L build-up for OI accuracy",
    }

    # Keep backward-compat keys for dashboard
    saved["standard"]      = saved["windows"][0]["standard"]
    saved["covid_excluded"] = saved["windows"][0]["covid_excluded"]

    print(f"\n{'='*60}")
    print(f"  AGGREGATE (COVID excl, component P&L, α=0.80)")
    print(f"{'='*60}")
    print(f"  Revenue MAPE:          {agg_mape:.1f}%")
    print(f"  Directional accuracy:  {agg_dir:.0f}%")
    if agg_gm_err is not None:
        print(f"  Avg GM error:          {agg_gm_err:.1f}pp")
    if agg_oi_mape is not None:
        print(f"  Avg OI MAPE:           {agg_oi_mape:.1f}%")
    print(f"{'='*60}")

    eval_path = _REPO_ROOT / "eval/backtest_results.json"
    eval_path.parent.mkdir(exist_ok=True)
    with open(eval_path, "w") as f:
        json.dump(saved, f, indent=2)
    print(f"\nEval results saved to {eval_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true", help="Run backtesting eval instead of interactive mode")
    args = parser.parse_args()

    if args.eval:
        run_eval_mode()
    else:
        run_interactive()
