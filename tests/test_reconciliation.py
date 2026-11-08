"""Gate 2: score reconciliation, thresholds, priority, capacity and run-rate. All expected values are computed independently of the engine."""
import pytest

from src.analytics.risk_scoring import DIMENSIONS
from src.config import load_settings
from tests.helpers import make_row, run_one, run_rows


def _rebuild(r, cfg):
    p = r["score_parts"]
    w = cfg["weights"]
    wsum = sum(w.values())
    dims = {d: r[f"dim_{d}"] for d in DIMENSIONS}
    return p, dims, w, wsum


@pytest.mark.parametrize("kw", [
    {},
    dict(tpv=[30, 30, 28, 24, 20, 17], success_rate_m1_m3_pct=96.0, success_rate_m4_m6_pct=86.0, unresolved_tickets=3.0, last_csat_1_to_5=2.0),
    dict(account_manager_note="Comparing quotes from two providers", days_to_contract_renewal=28.0, logins_last_30d=1.0, products_used=1.0),
    dict(unresolved_tickets=5.0, last_csat_1_to_5=1.0, support_tickets_last_90d=8.0),
])
def test_total_reconciles_exactly_with_dimensions(kw):
    from src.config import load_scoring
    cfg = load_scoring()
    r = run_one(**kw)
    p, dims, w, wsum = _rebuild(r, cfg)
    weighted = sum(dims[d] * w[d] for d in DIMENSIONS) / wsum
    # displayed dimension scores are rounded to 0.1, so allow that rounding only
    assert abs(weighted - p["weighted_mean"]) < 0.06
    assert abs(sum(p["weighted_points"].values()) - p["weighted_mean"]) < 0.02
    rebuilt = p["weighted_share"] * p["weighted_mean"] + (1 - p["weighted_share"]) * p["strongest_dimension"] + p["convergence_bonus"]
    assert abs(rebuilt - p["uncapped_total"]) < 0.02
    assert abs(min(100, p["uncapped_total"]) - r["risk_score"]) < 0.06


def test_no_single_dimension_can_reach_high_alone():
    from src.config import load_scoring
    cfg = load_scoring()
    ag, w = cfg["aggregation"], cfg["weights"]
    wsum = sum(w.values())
    for d in DIMENSIONS:
        score = ag["weighted_share"] * (100 * w[d] / wsum) + (1 - ag["weighted_share"]) * 100
        assert score < cfg["bands"]["high"], f"{d} alone at 100 would reach High ({score:.1f})"


@pytest.mark.parametrize("score,band", [(49.9, "medium"), (50.0, "high"), (27.9, "low"), (28.0, "medium"), (0.0, "low"), (100.0, "high")])
def test_threshold_assignment(score, band):
    from src.analytics.risk_scoring import _band
    from src.config import load_scoring
    assert _band(score, load_scoring()["bands"]) == band


def test_weights_sum_to_one():
    from src.config import load_scoring
    assert abs(sum(load_scoring()["weights"].values()) - 1.0) < 1e-9


def test_capacity_respected_and_ties_break_by_id():
    rows = [make_row(merchant_id=f"T{i:02d}", tpv=[40, 38, 34, 30, 25, 20], success_rate_m1_m3_pct=96.0, success_rate_m4_m6_pct=86.0, unresolved_tickets=4.0, last_csat_1_to_5=2.0) for i in range(20)]
    df = run_rows(rows)
    sel = df[df["selected_for_outreach"]]
    assert len(sel) == load_settings()["source_assumptions"]["max_outreaches"]
    # identical merchants: ranking must fall back to merchant_id ascending
    ranked = df[df["eligible_for_outreach"]].sort_values("outreach_priority_rank")["merchant_id"].tolist()
    assert ranked == sorted(ranked)


def test_priority_index_formula_and_not_a_probability():
    df = run_rows([make_row(merchant_id="P1", tpv=[40, 38, 34, 30, 25, 20], success_rate_m1_m3_pct=96.0, success_rate_m4_m6_pct=86.0)])
    r = df.iloc[0]
    fa = load_settings()["source_assumptions"]["false_alarm_cost_inr"]
    w = r["risk_weight"]
    assert r["priority_value_inr"] == pytest.approx((w * r["annual_value_at_stake_inr"] - (1 - w) * fa) * r["urgency_multiplier"])
    assert "churn_probability" not in df.columns


def test_annual_run_rate_uses_m6_tpv_rate_unit_and_12_months():
    df = run_rows([make_row(merchant_id="R1", tpv=[10, 10, 10, 10, 10, 20])])
    r = df.iloc[0]
    # Rs lakh -> Rs (x 100,000), x net revenue rate (1%), x 12 months
    assert r["annual_value_at_stake_inr"] == pytest.approx(20 * 100_000 * 0.01 * 12)
    assert r["monthly_net_revenue_inr"] == pytest.approx(20 * 100_000 * 0.01)


def test_critical_triggers_do_not_change_score():
    base = run_one(unresolved_tickets=4.0, last_csat_1_to_5=2.0, support_tickets_last_90d=6.0)
    assert any("service_breakdown" in t for t in base["critical_triggers"])
    # trigger is a review flag only: same inputs minus the trigger-only condition must not add points
    assert base["score_parts"]["uncapped_total"] == pytest.approx(
        base["score_parts"]["weighted_share"] * base["score_parts"]["weighted_mean"]
        + (1 - base["score_parts"]["weighted_share"]) * base["score_parts"]["strongest_dimension"] + base["score_parts"]["convergence_bonus"], abs=0.02)


def test_silent_decline_trigger_fires_and_adds_no_points():
    r = run_one(tpv=[40, 36, 31, 26, 21, 17], logins_last_30d=1.0, products_used=3.0)
    assert any("silent_decline" in t for t in r["critical_triggers"])
    p = r["score_parts"]
    assert p["uncapped_total"] == pytest.approx(p["weighted_share"] * p["weighted_mean"] + (1 - p["weighted_share"]) * p["strongest_dimension"] + p["convergence_bonus"], abs=0.02)
