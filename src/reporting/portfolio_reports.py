"""Portfolio-level (management) insights. Descriptive only: no causal claims."""
from __future__ import annotations

import pandas as pd

from src.analytics.risk_scoring import DRIVER_LABELS


def _lakh(inr: float) -> str:
    return f"Rs {inr / 1e5:,.1f} lakh"


def build_portfolio_md(df: pd.DataFrame, settings: dict, run_ts: str, sens_summary: pd.DataFrame, sens_overlap: pd.DataFrame) -> str:
    sa = settings["source_assumptions"]
    cap = sa["max_outreaches"]
    flagged = df[df["risk_band"].isin(["high", "medium"])]
    sel = df[df["selected_for_outreach"]].sort_values("outreach_priority_rank")
    L = [f"# Portfolio insights\n", f"_Run {run_ts} | config {settings['config_version']}_\n",
         "> **Read first.** Scores are a heuristic risk indication built from supplied signals. They are not churn probabilities and have not "
         "been validated against actual churn (labels are withheld). Revenue figures are **current run-rate exposure** (M6 TPV x 1% x 12), not guaranteed loss.\n"]

    L.append("## 1. Merchants by risk band\n")
    L.append("| Band | Merchants | Annual run-rate revenue exposure |\n|---|---|---|")
    for b in ("high", "medium", "low"):
        s = df[df["risk_band"] == b]
        L.append(f"| {b} | {len(s)} | {_lakh(s['annual_value_at_stake_inr'].sum())} |")

    L.append("\n## 2. Segment patterns\n")
    seg = df.groupby("segment").agg(merchants=("merchant_id", "count"), mean_risk=("risk_score", "mean"),
                                    high=("risk_band", lambda s: (s == "high").sum()), medium=("risk_band", lambda s: (s == "medium").sum()),
                                    exposure=("annual_value_at_stake_inr", "sum")).reset_index()
    L.append("| Segment | Merchants | Mean score | High | Medium | Total run-rate exposure |\n|---|---|---|---|---|---|")
    for _, r in seg.iterrows():
        L.append(f"| {r['segment']} | {r['merchants']} | {r['mean_risk']:.1f} | {r['high']} | {r['medium']} | {_lakh(r['exposure'])} |")

    L.append("\n## 3. Risk drivers among high/medium merchants (primary driver)\n")
    L.append("| Driver | Merchants | Examples |\n|---|---|---|")
    for dim, label in DRIVER_LABELS.items():
        s = flagged[flagged["primary_dimension"] == dim]
        L.append(f"| {label} | {len(s)} | {', '.join(s['merchant_id'].head(8))} |")
    L.append("\nDescriptive counts only; they do not establish that a driver *caused* any churn.\n")

    L.append("## 4. Renewal exposure (high/medium merchants)\n")
    L.append("| Renewal window | Merchants | Run-rate exposure |\n|---|---|---|")
    for band in ("<=30d", "31-60d", "61-90d", ">90d"):
        s = flagged[flagged["renewal_band"] == band]
        L.append(f"| {band} | {len(s)} | {_lakh(s['annual_value_at_stake_inr'].sum())} |")

    L.append("\n## 5. Decoy analysis (look risky, usually are not)\n")
    seasonal = df[df["is_seasonal_industry"] & (df["recent_vs_early_pct"] <= -10)]
    lowvol = df[(df["tpv_avg_m4_m6"] < 5) & (df["recent_vs_early_pct"] >= -10)]
    busy = df[(df["tickets_90d"] >= 5) & (df["unresolved"] <= 1) & (df["recent_vs_early_pct"] >= 5)]
    L.append("| Decoy type | Merchants | Flagged high/medium | Notes |\n|---|---|---|---|")
    for name, s in (("Seasonal industry with TPV dip (>=10%)", seasonal), ("Naturally low-volume and stable", lowvol), ("Busy-but-healthy (>=5 tickets, growing, <=1 open)", busy)):
        fl = s[s["risk_band"].isin(["high", "medium"])]
        L.append(f"| {name} | {len(s)} | {len(fl)} ({', '.join(fl['merchant_id'])}) | flagged ones have independent signals (see per-merchant evidence) |")
    L.append("\nSeasonality only discounts the TPV component of the performance dimension, and only for a dip-then-rebound shape in a listed seasonal industry. It never discounts service, engagement or commercial signals.")

    L.append("\n## 6. Most common fixable operational issues\n")
    sd = df[df["success_drop_pp"] <= -5]
    un = df[df["unresolved"] >= 3]
    lc = df[df["csat_low"]]
    cm = df[df["note_competitor_explicit"] | df["note_exploring_options"] | df["note_rate_card_request"]]
    ct = df[df["note_decision_maker_change"] | df["note_unresponsive"]]
    L += [f"- **Success-rate deterioration >=5pp:** {len(sd)} merchants ({', '.join(sd['merchant_id'])}).",
          f"- **>=3 unresolved tickets:** {len(un)} merchants ({', '.join(un['merchant_id'])}); {int(df['unresolved'].sum())} open tickets in total.",
          f"- **Low CSAT (<=2):** {len(lc)} merchants; CSAT missing for {int(df['csat_missing'].sum())} merchants (unknown, not poor).",
          f"- **Competitor / rate-card / 'exploring options' notes:** {len(cm)} merchants; {int((cm['renewal_days'] <= 60).sum())} renew within 60 days.",
          f"- **Contact change / unresponsive:** {len(ct)} merchants."]

    L.append("\n## 7. Suggested systemic improvements (hypotheses to validate, grounded in the counts above)\n")
    L += [f"1. **Payment-performance monitoring:** {len(sd)} merchants show a >=5pp success-rate drop; consider merchant-level success-rate alerts by method/bank so Payments Ops sees drops before volume moves.",
          f"2. **Ticket ageing:** {len(un)} merchants carry >=3 open tickets; consider an ageing alert and single-owner rule before CSAT falls.",
          f"3. **Earlier renewal reviews:** {int((cm['renewal_days'] <= 60).sum())} merchants with commercial signals renew within 60 days; consider starting the rate-card/volume-tier review at ~90 days.",
          f"4. **Contact hygiene:** {len(ct)} merchants show a contact change or silence; consider a periodic decision-maker re-confirmation touchpoint."]

    L.append(f"\n## 8. Outreach selection (cap {cap})\n")
    cost = len(sel) * sa["false_alarm_cost_inr"]
    L.append(f"- Selected: **{len(sel)}** merchants; combined run-rate revenue exposure {_lakh(sel['annual_value_at_stake_inr'].sum())}.")
    L.append(f"- Worst-case cost if every selected outreach were a false alarm: Rs {cost:,.0f} ({len(sel)} x Rs {sa['false_alarm_cost_inr']:,}).")
    L.append("- Break-even: one saved merchant is worth far more than the false-alarm cost for every selected merchant (smallest selected exposure "
             f"{_lakh(sel['annual_value_at_stake_inr'].min())} vs Rs {sa['false_alarm_cost_inr']:,}). This says nothing about the probability of saving.\n")
    L.append("| Outreach # | Merchant | Segment | Score | Playbook | Renewal (days) | Exposure |\n|---|---|---|---|---|---|---|")
    for _, r in sel.iterrows():
        L.append(f"| {int(r['outreach_priority_rank'])} | {r['merchant_id']} {r['business_name']} | {r['segment']} | {r['risk_score']:.0f} | {r['primary_playbook_id']} | {int(r['renewal_days'])} | {_lakh(r['annual_value_at_stake_inr'])} |")
    nxt = df[df["eligible_for_outreach"] & ~df["selected_for_outreach"]].sort_values("outreach_priority_rank")
    if len(nxt):
        c = nxt.iloc[0]
        last = sel.iloc[-1]
        L.append(f"\n**Why #{int(c['outreach_priority_rank'])} ({c['merchant_id']}) missed the cut:** priority proxy {_lakh(c['priority_value_inr'])} vs {_lakh(last['priority_value_inr'])} for #{int(last['outreach_priority_rank'])} ({last['merchant_id']}). "
                 f"{len(nxt)} eligible merchants are outside the cap and should stay on the watchlist.")

    L.append("\n## 9. Sensitivity of the selection\n")
    L.append("| Scenario | Selected | Overlap with baseline | Jaccard | Added | Dropped |\n|---|---|---|---|---|---|")
    for _, r in sens_overlap.iterrows():
        L.append(f"| {r['scenario']} | {r['selected']} | {r['overlap_with_baseline']} | {r['jaccard_vs_baseline']} | {r['added_vs_baseline']} | {r['dropped_vs_baseline']} |")
    stable = sens_summary[sens_summary["scenarios_selected"] == sens_summary["scenarios_total"]]
    L.append(f"\n{len(stable)} merchants are selected under **every** scenario: {', '.join(stable['merchant_id'])}.")
    return "\n".join(L) + "\n"
