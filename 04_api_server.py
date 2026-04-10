"""
AEO FP&A Agent — Step 4: API Server
=====================================
Wraps FPAAgent in a FastAPI server so the React dashboard can
send chat messages and receive real-time chart updates.

Run: uvicorn src.04_api_server:app --reload  (from aeo_fpa_agent/)
  OR: python src/04_api_server.py

Endpoints:
  POST /chat      { "message": "..." }
                  → { "response": "...", "intent": "...", "chart_update": {...} }
  GET  /summary   → { "summary": "3-sentence CFO briefing" }
  GET  /segments  → { "segments": [...] }
  GET  /peers     → { "peers": [...] }
  GET  /health    → { "status": "ok" }
  POST /reset     → clears conversation history
"""

import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any

import openai
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(_REPO_ROOT / ".env")
load_dotenv(find_dotenv())

# ── Import agent module via importlib (name starts with digit) ───────────────
_agent_path = Path(__file__).parent / "03_build_agent.py"
_spec = importlib.util.spec_from_file_location("build_agent", _agent_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

FPAAgent            = _module.FPAAgent
forecast_revenue    = _module.forecast_revenue
run_budget_scenario = _module.run_budget_scenario
flag_anomalies      = _module.flag_anomalies
calculate_ratios    = _module.calculate_ratios
compute_rolling_backtest_metrics = _module.compute_rolling_backtest_metrics

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="AEO FP&A Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# All API routes live on this router so they can be mounted at both
# "/" (local dev — Vite proxy strips /api) and "/api" (production)
router = APIRouter()

agent = FPAAgent()

# ── Session persistence ───────────────────────────────────────────────────
SESSION_PATH = Path(__file__).resolve().parent / ".session_history.json"


def _save_session():
    """Persist the user/assistant message pairs to disk (skip tool-call messages)."""
    try:
        serializable = []
        for msg in agent.history:
            if isinstance(msg, dict) and msg.get("role") in ("user", "assistant") and msg.get("content"):
                serializable.append({"role": msg["role"], "content": msg["content"]})
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_PATH, "w") as f:
            json.dump(serializable, f)
    except Exception:
        pass


def _load_session():
    """Restore saved session into agent history on startup."""
    if SESSION_PATH.exists():
        try:
            with open(SESSION_PATH) as f:
                saved = json.load(f)
            agent.history = saved
        except Exception:
            pass


_load_session()


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


# ── Intent detection ─────────────────────────────────────────────────────────

def detect_intent(message: str) -> str:
    msg = message.lower()
    if any(
        kw in msg
        for kw in [
            "forecast", "predict", "project", "next year", "fy2025", "fy2026", "fy2027",
            "2 year", "two year", "1 year", "one year", "3 year", "three year",
            "outlook", "projection", "guidance",
        ]
    ):
        return "forecast"
    if any(kw in msg for kw in ["what if", "scenario", "budget", "simulate", "comp sales", "comparable", "decline", "increase rev"]):
        return "budget"
    if any(kw in msg for kw in ["anomal", "unusual", "flag", "outlier", "pattern", "weird"]):
        return "anomaly"
    if any(kw in msg for kw in ["compar", "anf", "gap", "peer", "competitor", "benchmark",
                                  "abercrombie", "vs ", "versus", "industry"]):
        return "peer_comparison"
    if any(kw in msg for kw in ["aerie", "ae brand", "segment", "brand mix", "brand split", "aeo segment"]):
        return "segment"
    if any(kw in msg for kw in ["ratio", "roe", "roa", "inventory turn", "dsi", "fcf margin", "efficient", "asset"]):
        return "ratios"
    if any(kw in msg for kw in ["quarter", "q1", "q2", "q3", "q4", "seasonal", "quarterly"]):
        return "quarterly"
    if any(kw in msg for kw in ["why did", "what drove", "margin bridge", "decompos", "causal", "driver"]):
        return "margin_bridge"
    return "general"


# ── Chart data builders ───────────────────────────────────────────────────────

def parse_forecast_params(message: str) -> dict:
    """
    Derive horizon, COVID training exclusion, and α from the user's message so charts and
    backtest match the same assumptions as their forecast question.
    """
    msg = message.lower()

    if re.search(r"\b(next\s+)?(three|3)\s+years?\b", msg):
        years_out = 3
    elif re.search(r"\b(next\s+)?(two|2)\s+years?\b", msg) or re.search(r"\bnext\s+2\s+years?\b", msg):
        years_out = 2
    elif (
        re.search(r"\b(next\s+year|next\s+1\s+years?)\b", msg)
        or re.search(r"\b(one|1)[\s-]+year\b", msg)
        or re.search(r"\bsingle\s+year\b", msg)
    ):
        years_out = 1
    else:
        years_out = 2

    exclude = [2020]
    if re.search(r"\b(include|with|retain)\s+(covid|fy\s*20|2020)\b", msg):
        exclude = []
    if re.search(r"\b(exclude|without|excluding)\s+(covid|fy\s*20|2020)\b", msg):
        exclude = [2020]

    alpha = 0.80
    ma = re.search(r"\balpha\s*[=:]?\s*(0\.\d{1,2})\b", msg)
    if ma:
        alpha = max(0.50, min(0.99, float(ma.group(1))))

    return {"years_out": years_out, "exclude_fiscal_years": exclude, "alpha": alpha}


def build_forecast_chart(records: list[dict], message: str) -> dict:
    """Base/bull/bear revenue path + margins; horizon/settings parsed from the user message."""
    p = parse_forecast_params(message)
    years_out = p["years_out"]
    scenarios: dict[str, list] = {}
    for scenario in ["base", "bull", "bear"]:
        result = forecast_revenue(
            records,
            years_out=years_out,
            scenario=scenario,
            exclude_fiscal_years=p["exclude_fiscal_years"],
            alpha=p["alpha"],
        )
        if result.get("error"):
            return {"type": "forecast", "error": result["error"], "forecast_params": p, "data": [], "backtest": None}
        scenarios[scenario] = result.get("forecasts", [])

    data = []
    base_fcs = scenarios.get("base", [])
    for i, bf in enumerate(base_fcs):
        fy = bf["fiscal_year"]
        bull_fc = scenarios["bull"][i] if i < len(scenarios.get("bull", [])) else {}
        bear_fc = scenarios["bear"][i] if i < len(scenarios.get("bear", [])) else {}
        data.append({
            "label":   f"FY{fy}",
            "base":    round(bf["projected_revenue_000s"] / 1e3, 1),
            "bull":    round(bull_fc.get("projected_revenue_000s", 0) / 1e3, 1),
            "bear":    round(bear_fc.get("projected_revenue_000s", 0) / 1e3, 1),
            "base_gm": bf.get("projected_gross_margin_pct"),
            "base_om": bf.get("projected_operating_margin_pct"),
            "base_oi": round(bf.get("projected_operating_income_000s", 0) / 1e3, 1),
            "base_sga": round(bf.get("projected_sga_000s", 0) / 1e3, 1),
            "base_cogs": round(bf.get("projected_cogs_000s", 0) / 1e3, 1),
        })

    backtest = None
    try:
        backtest = compute_rolling_backtest_metrics(
            records,
            years_out=years_out,
            exclude_fiscal_years=p["exclude_fiscal_years"],
            alpha=p["alpha"],
        )
    except Exception:
        pass

    return {
        "type": "forecast",
        "data": data,
        "model": "component_pnl",
        "forecast_params": p,
        "backtest": backtest,
    }


def build_budget_chart(records: list[dict], message: str) -> dict:
    """Parse revenue % change from the message and compute a budget scenario bar."""
    rev_match = re.search(r"([+-]?\d+\.?\d*)\s*%", message)
    rev_change = float(rev_match.group(1)) if rev_match else -3.0
    # Treat "decline X%" as negative
    if any(kw in message.lower() for kw in ["decline", "drop", "decrease", "fall", "down"]):
        rev_change = -abs(rev_change)

    base = records[-1]
    result = run_budget_scenario(base, revenue_change_pct=rev_change)
    proj = result.get("projected", {})
    return {
        "type": "budget",
        "label": f"What-if ({rev_change:+.1f}%)",
        "revenue": round(proj.get("net_revenue_000s", 0) / 1e3, 1),
        "op_margin": proj.get("operating_margin_pct"),
        "rev_change": rev_change,
    }


def build_anomaly_chart(records: list[dict]) -> dict:
    """Return the fiscal years with detected anomalies."""
    flags = flag_anomalies(records)
    flagged_years = list({f["fiscal_year"] for f in flags})
    return {"type": "anomaly", "flagged_years": flagged_years}


def build_peer_chart(peer_records: list[dict]) -> dict:
    """
    Build a peer margin comparison dataset for overlay on the margin line chart.
    Returns last 5 years for AEO's primary comps (ANF, GPS).
    """
    from collections import defaultdict
    by_ticker: dict[str, dict] = defaultdict(dict)
    for r in peer_records:
        label = r.get("label", "")
        # Only include recent years to avoid chart clutter
        if label >= "FY2020":
            by_ticker[r["ticker"]][label] = {
                "gross_margin_pct":    r.get("gross_margin_pct"),
                "operating_margin_pct": r.get("operating_margin_pct"),
                "net_revenue_M":       round(r["net_revenue"] / 1e3, 1) if r.get("net_revenue") else None,
            }
    return {"type": "peer_comparison", "peers": dict(by_ticker)}


def build_segment_chart(segment_records: list[dict]) -> dict:
    """Return AE vs Aerie stacked bar data for the dashboard."""
    data = []
    for r in segment_records:
        if r.get("aerie_revenue") and r.get("ae_revenue"):
            data.append({
                "label":        r["label"],
                "aerie":        round(r["aerie_revenue"] / 1e3, 1),
                "ae":           round(r["ae_revenue"] / 1e3, 1),
                "aerie_share":  r.get("aerie_share_pct"),
                "aerie_oi_m":   r.get("aerie_oi_margin_pct"),
                "ae_oi_m":      r.get("ae_oi_margin_pct"),
            })
    return {"type": "segment", "data": data}


def build_ratios_chart(records: list[dict]) -> dict:
    """Return key ratios for FY2022–FY2024 for the dashboard."""
    data = []
    for r in records:
        fy = r.get("fiscal_year")
        if fy and fy >= 2022:
            ratios = calculate_ratios(records, fy)
            data.append({"label": f"FY{fy}", **ratios})
    return {"type": "ratios", "data": data}


def get_chart_update(
    intent: str,
    records: list[dict],
    peer_records: list[dict],
    segment_records: list[dict],
    message: str,
) -> dict | None:
    if not records:
        return None
    try:
        if intent == "forecast":
            return build_forecast_chart(records, message)
        if intent == "budget":
            return build_budget_chart(records, message)
        if intent == "anomaly":
            return build_anomaly_chart(records)
        if intent == "peer_comparison" and peer_records:
            return build_peer_chart(peer_records)
        if intent == "segment" and segment_records:
            return build_segment_chart(segment_records)
        if intent == "ratios":
            return build_ratios_chart(records)
    except Exception:
        pass
    return None


# ── Suggestions parser ───────────────────────────────────────────────────────

def parse_suggestions(text: str) -> tuple[str, list[str]]:
    """
    Pull follow-up bullets into `suggestions` and leave a single canonical line
    **Suggested next steps:** in the body (renders as bold in the UI, no stray asterisks).
    """
    text = re.sub(r'\\([*#_`\[\]])', r"\1", text)

    # Heading + bullets on following lines
    block_nl = re.compile(
        r"\s*\*{0,2}\s*Suggested next steps:\s*\*{0,2}\s*\n((?:\s*[-•*]\s*.+\n?)+)",
        re.IGNORECASE,
    )
    # Heading immediately followed by bullets (no newline after colon)
    block_inline = re.compile(
        r"\s*\*{0,2}\s*Suggested next steps:\s*\*{0,2}\s*((?:\s*[-•*]\s*.+(?:\n|$))+)",
        re.IGNORECASE,
    )

    for pattern in (block_nl, block_inline):
        match = pattern.search(text)
        if not match:
            continue
        bullet_block = match.group(1)
        items = re.findall(r"[-•*]\s*(.+)", bullet_block)
        suggestions = [s.strip().strip('"').strip("'") for s in items if s.strip()]
        suggestions = suggestions[:3]
        cleaned = text[: match.start()].rstrip() + "\n\n**Suggested next steps:**\n" + text[match.end() :].lstrip()
        return cleaned.strip(), suggestions

    return text.strip(), []


def polish_response_body(text: str) -> str:
    """Normalize any remaining 'Suggested next steps' wrappers to one bold-markdown line."""
    if not text:
        return text
    text = re.sub(
        r"\s*\*{1,2}\s*Suggested next steps:\s*\*{1,2}\s*",
        "\n\n**Suggested next steps:**\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:\n\n\*\*Suggested next steps:\*\*\n)+",
        "\n\n**Suggested next steps:**\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\*{3,}", "**", text)
    return text.strip()


# ── Schemas ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    intent: str = "general"
    chart_update: Any = None
    suggestions: list[str] = []


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/forecast-backtest")
def forecast_backtest_default(
    years_out: int = 2,
    exclude_covid: bool = True,
    alpha: float = 0.80,
):
    """
    Default holdout metrics (2Y horizon, FY2020 excluded, α=0.80) for the dashboard card on load.
    """
    if not agent.records:
        return {"backtest": None}
    excl = [2020] if exclude_covid else []
    a = max(0.50, min(0.99, float(alpha)))
    try:
        bt = compute_rolling_backtest_metrics(
            agent.records,
            years_out=years_out,
            exclude_fiscal_years=excl,
            alpha=a,
        )
    except Exception:
        bt = None
    return {"backtest": bt}


_summary_cache: dict = {"text": None, "insights": [], "suggestions": [], "dirty": True}


def _scan_insights() -> list[str]:
    """
    Scan AEO historical data + segments + peers for notable patterns.
    Returns a list of concise, data-driven insight strings.
    """
    import statistics

    insights: list[str] = []
    recs = sorted(agent.records, key=lambda r: r.get("fiscal_year", 0))

    if len(recs) < 3:
        return insights

    latest = recs[-1]
    prior  = recs[-2]
    fy     = latest.get("fiscal_year", "?")

    # ── Y/Y revenue change vs. historical norm ─────────────────────────
    yoy_revs = []
    for i in range(1, len(recs)):
        prev_rev = recs[i-1].get("net_revenue", 0)
        cur_rev  = recs[i].get("net_revenue", 0)
        if prev_rev > 0 and cur_rev > 0:
            yoy_revs.append((cur_rev - prev_rev) / prev_rev * 100)
    if len(yoy_revs) >= 4:
        latest_yoy = yoy_revs[-1]
        hist_mean  = statistics.mean(yoy_revs[:-1])
        hist_std   = statistics.stdev(yoy_revs[:-1]) if len(yoy_revs) > 2 else abs(hist_mean) * 0.3
        if abs(latest_yoy - hist_mean) > 1.5 * hist_std:
            direction = "above" if latest_yoy > hist_mean else "below"
            insights.append(
                f"FY{fy} revenue growth ({latest_yoy:+.1f}%) is significantly {direction} "
                f"the historical average ({hist_mean:+.1f}%)"
            )

    # ── GM% swing ──────────────────────────────────────────────────────
    gm_latest = latest.get("gross_margin_pct")
    gm_prior  = prior.get("gross_margin_pct")
    if gm_latest and gm_prior:
        gm_delta = gm_latest - gm_prior
        if abs(gm_delta) > 1.5:
            verb = "expanded" if gm_delta > 0 else "contracted"
            insights.append(
                f"Gross margin {verb} {abs(gm_delta):.1f}pp Y/Y to {gm_latest:.1f}% in FY{fy}"
            )

    # ── OI swing ───────────────────────────────────────────────────────
    oi_latest = latest.get("operating_income", 0)
    oi_prior  = prior.get("operating_income", 0)
    if oi_prior and oi_prior != 0:
        oi_change = (oi_latest - oi_prior) / abs(oi_prior) * 100
        if abs(oi_change) > 25:
            direction = "surged" if oi_change > 0 else "declined"
            insights.append(
                f"Operating income {direction} {abs(oi_change):.0f}% Y/Y to "
                f"${oi_latest / 1e3:,.0f}M in FY{fy}"
            )

    # ── Aerie share threshold ──────────────────────────────────────────
    if agent.segment_records:
        seg_sorted = sorted(agent.segment_records, key=lambda s: s.get("label", ""))
        if seg_sorted:
            latest_seg = seg_sorted[-1]
            aerie_share = latest_seg.get("aerie_share_pct")
            seg_label = latest_seg.get("label", "?")
            if aerie_share and aerie_share > 30:
                insights.append(
                    f"Aerie hit {aerie_share:.1f}% revenue share in {seg_label} — highest ever"
                )

    # ── Peer margin comparison ─────────────────────────────────────────
    if agent.peer_records:
        aeo_gm = gm_latest or 0
        peer_by_ticker: dict = {}
        for p in agent.peer_records:
            tk = p.get("ticker", "")
            if tk and p.get("gross_margin_pct"):
                peer_by_ticker[tk] = p.get("gross_margin_pct", 0)
        for tk, pgm in peer_by_ticker.items():
            if pgm > aeo_gm + 5:
                insights.append(
                    f"{tk} gross margin ({pgm:.1f}%) exceeds AEO ({aeo_gm:.1f}%) by {pgm - aeo_gm:.1f}pp"
                )
                break  # only surface the most notable

    # ── SGA ratio change ───────────────────────────────────────────────
    sga_latest = latest.get("sga_expense", 0)
    sga_prior  = prior.get("sga_expense", 0)
    rev_latest = latest.get("net_revenue", 1)
    rev_prior  = prior.get("net_revenue", 1)
    if sga_latest > 0 and sga_prior > 0:
        sga_pct_now  = sga_latest / rev_latest * 100
        sga_pct_prev = sga_prior  / rev_prior  * 100
        delta = sga_pct_now - sga_pct_prev
        if abs(delta) > 0.5:
            direction = "rose" if delta > 0 else "fell"
            insights.append(
                f"SGA-to-revenue ratio {direction} {abs(delta):.1f}pp to {sga_pct_now:.1f}% in FY{fy}"
            )

    return insights[:5]


def _compute_suggestions() -> list[dict]:
    """
    Pre-compute data-driven suggestions with actual numbers.
    Each suggestion has a 'label' (display text) and 'query' (message to send to agent).
    """
    suggestions: list[dict] = []
    recs = sorted(agent.records, key=lambda r: r.get("fiscal_year", 0))
    if len(recs) < 2:
        return suggestions

    latest = recs[-1]
    fy = latest.get("fiscal_year", 2024)

    # 1. Margin bridge — always relevant after new earnings
    oi_curr = latest.get("operating_income", 0)
    oi_prev = recs[-2].get("operating_income", 0)
    if oi_prev:
        oi_change_pct = (oi_curr - oi_prev) / abs(oi_prev) * 100
        suggestions.append({
            "label": f"Why did OI {'jump' if oi_change_pct > 0 else 'drop'} {abs(oi_change_pct):.0f}% in FY{fy}?",
            "query": f"Break down the drivers of the FY{fy} operating income change vs FY{fy-1}",
        })

    # 2. Forecast with actual numbers
    try:
        fc = forecast_revenue(recs, years_out=1, scenario="base", exclude_fiscal_years=[2020])
        if fc.get("forecasts"):
            f1 = fc["forecasts"][0]
            rev_m = f1["projected_revenue_000s"] / 1e3
            suggestions.append({
                "label": f"FY{fy+1} forecast: ${rev_m:,.0f}M revenue — stress test it",
                "query": f"Forecast revenue for FY{fy+1} and FY{fy+2} with base, bull, and bear scenarios",
            })
    except Exception:
        pass

    # 3. Aerie share milestone
    if agent.segment_records:
        seg_sorted = sorted(agent.segment_records, key=lambda s: s.get("label", ""))
        if seg_sorted:
            latest_seg = seg_sorted[-1]
            share = latest_seg.get("aerie_share_pct", 0)
            if share > 30:
                suggestions.append({
                    "label": f"Aerie is {share:.0f}% of revenue — what if growth slows to 2%?",
                    "query": f"What happens to AEO's total revenue if Aerie growth decelerates from its recent trend to just 2% annually?",
                })

    # 4. Peer gap analysis with actual numbers
    if agent.peer_records:
        aeo_gm = latest.get("gross_margin_pct", 0)
        best_peer = max(
            (p for p in agent.peer_records if p.get("gross_margin_pct")),
            key=lambda p: p.get("gross_margin_pct", 0),
            default=None,
        )
        if best_peer and best_peer.get("gross_margin_pct", 0) > aeo_gm:
            gap = best_peer["gross_margin_pct"] - aeo_gm
            tk = best_peer.get("ticker", "peer")
            suggestions.append({
                "label": f"{tk} GM is {gap:.0f}pp above AEO — what would it take to close?",
                "query": f"What gross margin does AEO need to match {tk}'s {best_peer['gross_margin_pct']:.1f}% GM, and what would that mean for operating income?",
            })

    # 5. Quarterly seasonality
    if agent.quarterly_records:
        q_sorted = sorted(agent.quarterly_records, key=lambda q: q.get("period_end", ""))
        if len(q_sorted) >= 4:
            latest_q = q_sorted[-1]
            q_label = latest_q.get("label", "?")
            q_rev = latest_q.get("net_revenue", 0) / 1e6
            suggestions.append({
                "label": f"Latest quarter ({q_label}): ${q_rev:,.0f}M — show quarterly trends",
                "query": f"Show me the quarterly revenue and margin trends for the most recent fiscal year",
            })

    return suggestions[:4]


def _fallback_summary_text() -> str:
    """Deterministic briefing when OPENAI_API_KEY is not set (dashboard still loads)."""
    recs = sorted(agent.records, key=lambda r: r.get("fiscal_year", 0))
    if len(recs) < 2:
        return (
            "Financial data is loading or unavailable. Run the data pipeline scripts if "
            "`data/processed/aeo_financials.json` is missing."
        )
    latest, prior = recs[-1], recs[-2]
    fy = latest.get("fiscal_year", "?")
    rev = latest.get("net_revenue", 0) / 1e3
    rev_p = prior.get("net_revenue", 0) / 1e3
    yoy = ((latest.get("net_revenue", 0) - prior.get("net_revenue", 0)) / prior.get("net_revenue", 1) * 100) if prior.get("net_revenue") else 0
    gm = latest.get("gross_margin_pct")
    om = latest.get("operating_margin_pct")
    margin_bits = []
    if gm is not None:
        margin_bits.append(f"gross margin {gm:.1f}%")
    if om is not None:
        margin_bits.append(f"operating margin {om:.1f}%")
    margin_str = ", ".join(margin_bits) if margin_bits else "margin metrics n/a"
    return (
        f"FY{fy} net revenue was ${rev:,.0f}M vs ${rev_p:,.0f}M prior year ({yoy:+.1f}% Y/Y), "
        f"with {margin_str}. "
        "Add OPENAI_API_KEY to `.env` for a full AI-generated executive narrative and chat."
    )


def _generate_summary() -> str:
    """
    Call the LLM with a tight prompt to produce a 3-sentence CFO-level briefing
    on AEO's FY2024 results. Cached — refreshed on first request and after each chat.
    """
    if not _has_openai_key():
        return _fallback_summary_text()
    system = agent.system_prompt
    prompt = (
        "You are a CFO preparing a one-paragraph executive briefing for a board meeting. "
        "In exactly 3 sentences: (1) summarize AEO's FY2024 financial performance vs FY2023, "
        "citing specific numbers; (2) highlight Aerie's brand growth story; "
        "(3) name the single most important forward-looking risk. "
        "Be direct, data-driven, and no fluff. Use only the data in your context."
    )
    try:
        # Shorter timeout than chat so the dashboard does not sit on a blank loader
        fast_client = openai.OpenAI(timeout=25.0, max_retries=1)
        resp = fast_client.chat.completions.create(
            model=_module.MODEL,
            max_tokens=220,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception:
        return _fallback_summary_text()


@router.get("/summary")
def get_summary():
    """Return executive briefing + data-driven insights + pre-computed suggestions."""
    if _summary_cache["dirty"] or not _summary_cache["text"]:
        try:
            _summary_cache["text"]        = _generate_summary()
            _summary_cache["insights"]    = _scan_insights()
            _summary_cache["suggestions"] = _compute_suggestions()
            _summary_cache["dirty"]       = False
        except Exception as e:
            return {"summary": f"(Summary unavailable: {e})", "insights": [], "suggestions": []}
    return {
        "summary": _summary_cache["text"],
        "insights": _summary_cache["insights"],
        "suggestions": _summary_cache["suggestions"],
    }


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        intent = detect_intent(message)
        chart_update = get_chart_update(
            intent, agent.records, agent.peer_records, agent.segment_records, message
        )
        if not _has_openai_key():
            response = (
                "**OpenAI API key not set.** Add `OPENAI_API_KEY=sk-...` to a `.env` file in the "
                "project root, then restart the API server (`python3 src/04_api_server.py`). "
                "Keyword-based chart updates (forecast, what-if scenarios, peers, etc.) still work."
            )
            agent.history.append({"role": "user", "content": message})
            agent.history.append({"role": "assistant", "content": response})
            _summary_cache["dirty"] = True
            _save_session()
            return ChatResponse(
                response=response,
                intent=intent,
                chart_update=chart_update,
                suggestions=[],
            )
        raw_response = agent.chat(message)
        response, suggestions = parse_suggestions(raw_response)
        response = polish_response_body(response)
        _summary_cache["dirty"] = True
        _save_session()
        return ChatResponse(
            response=response,
            intent=intent,
            chart_update=chart_update,
            suggestions=suggestions,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/peers")
def get_peers():
    """Return peer financial data for dashboard charts."""
    return {"peers": agent.peer_records}


@router.get("/segments")
def get_segments():
    """Return AE brand vs Aerie brand segment breakdown."""
    return {"segments": agent.segment_records}


@router.get("/quarterly")
def get_quarterly():
    """Return quarterly financial data."""
    return {"quarterly": agent.quarterly_records}


@router.get("/history")
def get_history():
    """Return saved conversation history for session restore."""
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in agent.history
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")
    ]
    return {"messages": messages}


@router.post("/reset")
def reset():
    agent.history.clear()
    _summary_cache["dirty"] = True
    if SESSION_PATH.exists():
        SESSION_PATH.unlink()
    return {"status": "reset"}


# ── Register routes ───────────────────────────────────────────────────────────
# Mount at "/" for local dev (Vite proxy strips /api before forwarding)
# Mount at "/api" for production (React calls /api/* directly against FastAPI)
app.include_router(router)
app.include_router(router, prefix="/api")

# ── Serve built React frontend (production) ───────────────────────────────────
_DIST = _REPO_ROOT / "dist"
if _DIST.exists():
    # Serve hashed asset files
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        """Return the requested file if it exists, otherwise serve index.html (SPA routing)."""
        target = _DIST / full_path
        if target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(_DIST / "index.html")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
