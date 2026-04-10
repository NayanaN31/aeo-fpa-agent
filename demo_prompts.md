# AEO FP&A Agent — Prompt Library
# =====================================
# These are tested prompts for the demo and strategy pitch.
# Use them to show the SVP what the agent can actually do.
# Format: CATEGORY > LABEL > PROMPT > EXPECTED BEHAVIOR

# -----------------------------------------------------------------------
# SECTION 1: Revenue & Margin Analysis
# -----------------------------------------------------------------------

[revenue_trend]
prompt = "Walk me through AEO's net revenue trajectory from FY2019 to FY2024. Highlight any years with unusual growth or contraction and explain what drove them."
expected = Agent cites COVID impact in FY2020, strong recovery in FY2021, and the Quiet Platforms writedown in FY2022. References specific dollar figures and growth rates.

[gross_margin_analysis]
prompt = "Has AEO been able to maintain gross margin over the last 5 years, or has it been under pressure? What's the trend and what drives it in retail?"
expected = Discusses inventory management improvements (the AI tool deployed in 2023), transportation cost normalization post-COVID, and markdown reduction strategy.

[segment_breakdown]
prompt = "Break down AEO's performance by segment — American Eagle vs. Aerie. Which is growing faster and what does that imply for the budget mix going forward?"
expected = Identifies Aerie as the higher-growth segment, discusses #AerieReal brand momentum, and connects to strategic priority of growing underpenetrated markets.

# -----------------------------------------------------------------------
# SECTION 2: Forecasting & Budgeting
# -----------------------------------------------------------------------

[base_case_forecast]
prompt = "Generate a 2-year revenue forecast for AEO using a base, bull, and bear scenario. Show your assumptions explicitly."
expected = Returns structured 3-scenario table with growth rate assumptions, references historical CAGR, flags macro risks (consumer spending, fashion cycles).

[comp_sales_scenario]
prompt = "Build a budget scenario where comparable sales decline 3% next year. How does that flow through to gross profit and operating income? What levers does management have to protect margins?"
expected = Runs budget_scenario tool, shows P&L waterfall, then discusses inventory reduction, SG&A leverage, and promotional management as levers.

[capex_planning]
prompt = "AEO has been investing in flagship stores. If they increase capital expenditure by 15% next year, how does that affect free cash flow and their capacity to return capital to shareholders?"
expected = Computes FCF impact, references current dividend + buyback program, discusses trade-off between growth investment and shareholder returns.

[store_count_scenario]
prompt = "If AEO closes 50 underperforming stores next year and the remaining stores average the same revenue per store as FY2023, what's the revenue impact?"
expected = Uses total_stores and revenue_per_store metrics, computes approximate revenue reduction, contextualizes against digital channel offset.

# -----------------------------------------------------------------------
# SECTION 3: Variance & Anomaly Detection
# -----------------------------------------------------------------------

[flag_anomalies]
prompt = "Scan AEO's financial history and flag any metrics that showed unusual year-over-year changes. For each flag, give a likely explanation."
expected = Triggers anomaly detection tool, flags FY2020 COVID revenue drop, FY2021 inventory surge, FY2022 Quiet Platforms impairment impact.

[fy2022_deep_dive]
prompt = "FY2022 looks like an outlier year for AEO. What happened to margins and operating income? Walk me through the reconciliation between gross profit and the operating income line."
expected = References the Quiet Platforms restructuring ($98M+ in impairments), distinguishes GAAP vs. adjusted operating income, explains one-time charges.

[inventory_health]
prompt = "AEO has talked publicly about inventory as a key operational focus. How have inventory levels trended relative to revenue? Is the ratio improving?"
expected = Calculates inventory-to-revenue ratio by year, shows post-COVID improvement, connects to the AI inventory tool they deployed and margin recovery.

# -----------------------------------------------------------------------
# SECTION 4: The "Why Don't We Do This Internally?" Demo
# -----------------------------------------------------------------------
# These prompts are designed to directly make the case to the SVP
# by showing tasks his team currently does manually in Excel.

[monthly_close_narrative]
prompt = "Draft a management commentary narrative for a hypothetical FY2025 Q1 result where revenue was $1.2B, up 2% YoY, but gross margin contracted 80bps due to higher promotional activity. Format it as it would appear in an earnings release."
expected = Produces professional management commentary with specific numbers, drivers, and forward-looking language — the kind of narrative an analyst spends hours writing.

[board_deck_bullets]
prompt = "Generate 5 CFO-ready bullet points summarizing AEO's FY2024 financial performance for a board presentation. Each bullet should have the key metric and one sentence of context."
expected = Produces crisp, executive-ready bullets that reference specific FY2024 numbers and strategic context.

[budget_review_prep]
prompt = "I'm preparing for our annual budget review meeting. Give me the 5 most important financial questions the CEO and board are likely to ask about next year's plan, and for each question, what data we should have ready."
expected = Produces a question preparation guide grounded in AEO's actual financial dynamics — not generic finance questions.

[reconciliation_check]
prompt = "Check these numbers for internal consistency and flag anything that looks off: Revenue $4.8B, Cost of Sales $2.9B, Gross Profit $1.95B, SG&A $1.2B, Operating Income $720M."
expected = Flags that $4.8B - $2.9B = $1.9B not $1.95B (arithmetic error), and that $1.95B - $1.2B = $750M not $720M. Also flags that 15% operating margin would be high for AEO historically.

# -----------------------------------------------------------------------
# SECTION 5: Eval / Backtesting Prompts
# -----------------------------------------------------------------------

[backtest_explain]
prompt = "I trained you on AEO's financials from FY2015 to FY2020 only. Now predict what FY2021 revenue and gross margin would be, using only what you knew as of early 2021."
expected = Makes explicit assumptions (pre-COVID base, uncertain recovery), gives a range, then after revealed actuals can explain what it got right/wrong.

[prediction_reasoning]
prompt = "Using only FY2015–FY2019 data (pre-COVID baseline), what was your prediction for FY2020 revenue? Now that we know actual FY2020 revenue was approximately $3.2B (down from $4.3B in FY2019), what does that miss tell us about the limits of trend-based forecasting?"
expected = Discusses black swan events, model limitations, importance of scenario planning + qualitative inputs — makes a sophisticated point about AI + human judgment.
