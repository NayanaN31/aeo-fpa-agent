#!/usr/bin/env python3
"""
Write public/static-demo.json for GitHub Pages (no API).
Run from repo root: python3 scripts/export_static_demo.py
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PUBLIC.mkdir(exist_ok=True)

_agent = ROOT / "src" / "03_build_agent.py"
spec = importlib.util.spec_from_file_location("build_agent", _agent)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

agent = mod.FPAAgent()
recs = sorted(agent.records, key=lambda r: r.get("fiscal_year", 0))
latest, prior = recs[-1], recs[-2] if len(recs) >= 2 else recs[-1]
fy = latest.get("fiscal_year", "?")
rev = latest.get("net_revenue", 0) / 1e3
rev_p = prior.get("net_revenue", 0) / 1e3
yoy = (
    (latest.get("net_revenue", 0) - prior.get("net_revenue", 0))
    / prior.get("net_revenue", 1)
    * 100
    if prior.get("net_revenue")
    else 0
)
gm = latest.get("gross_margin_pct")
om = latest.get("operating_margin_pct")
margin_bits = []
if gm is not None:
    margin_bits.append(f"gross margin {gm:.1f}%")
if om is not None:
    margin_bits.append(f"operating margin {om:.1f}%")
margin_str = ", ".join(margin_bits) if margin_bits else "margin metrics n/a"

summary = (
    f"FY{fy} net revenue was ${rev:,.0f}M vs ${rev_p:,.0f}M prior year ({yoy:+.1f}% Y/Y), "
    f"with {margin_str} (AEO 10-K, thousands USD as reported). "
    "This public build is static — run the FastAPI app locally or host the API to enable live AI chat."
)

bt = mod.compute_rolling_backtest_metrics(
    agent.records,
    years_out=2,
    exclude_fiscal_years=[2020],
    alpha=0.80,
)

out = {
    "summary": summary,
    "insights": [],
    "suggestions": [],
    "backtest": bt,
}

path = PUBLIC / "static-demo.json"
path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"Wrote {path}")
