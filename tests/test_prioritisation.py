import pandas as pd

from src.analytics.prioritisation import prioritise
from src.analytics.sensitivity import run_sensitivity
from src.pipeline import build_frame


def test_all_100_merchants_receive_a_result(built):
    _, _, df = built
    assert len(df) == 100 and df["merchant_id"].is_unique
    assert sorted(df["risk_rank"]) == list(range(1, 101))


def test_at_most_15_selected_and_ranks_are_separate(built):
    _, _, df = built
    sel = df[df["selected_for_outreach"]]
    assert 0 < len(sel) <= 15
    assert df["outreach_priority_rank"].notna().sum() <= df["eligible_for_outreach"].sum()
    # outreach ranking differs from the risk ranking (value-weighted), and only exists for eligible merchants
    e = df[df["eligible_for_outreach"]].sort_values("outreach_priority_rank")
    assert list(e["risk_rank"]) != sorted(e["risk_rank"])


def test_selection_is_deterministic(cfgs):
    a = build_frame(*cfgs)[2]
    b = build_frame(*cfgs)[2]
    assert list(a.loc[a.selected_for_outreach, "merchant_id"]) == list(b.loc[b.selected_for_outreach, "merchant_id"])
    pd.testing.assert_series_equal(a["risk_score"], b["risk_score"])


def test_selected_have_evidence_and_supported_playbook(built):
    _, _, df = built
    for _, r in df[df["selected_for_outreach"]].iterrows():
        assert r["primary_playbook_id"] in ("PB-1", "PB-2", "PB-3", "PB-4")
        assert r["playbook_trigger_reason"] and r["risk_band"] in ("high", "medium")


def test_exclusion_of_first_unselected_is_explained(built):
    _, _, df = built
    nxt = df[df["eligible_for_outreach"] & ~df["selected_for_outreach"]].sort_values("outreach_priority_rank")
    if len(nxt):
        assert "outside the 15-contact capacity" in nxt.iloc[0]["outreach_reason"]
        last = df[df["outreach_priority_rank"] == 15].iloc[0]
        assert nxt.iloc[0]["priority_value_inr"] <= last["priority_value_inr"]


def test_run_rate_value_uses_source_formula(built):
    _, _, df = built
    r = df.iloc[0]
    assert r["annual_value_at_stake_inr"] == r["tpv_m6_inr_lakh"] * 100000 * 0.01 * 12


def test_sensitivity_report_shape(built, cfgs):
    settings, scoring, pb = cfgs
    src, feats, _ = built
    long, summ, overlap = run_sensitivity(feats, scoring, pb, src.playbooks, settings)
    assert len(overlap) >= 10 and "baseline" in set(overlap["scenario"])
    assert (long.groupby("scenario")["selected_for_outreach"].sum() <= 15).all()
    assert len(summ) == 100


def test_decoys_not_selected(built):
    _, _, df = built
    seasonal_dip = df[df["seasonal_adjustment_applied"]]
    assert not seasonal_dip["selected_for_outreach"].any()
    busy = df[(df["tickets_90d"] >= 5) & (df["unresolved"] <= 1) & (df["recent_vs_early_pct"] >= 5)]
    assert not busy["selected_for_outreach"].any()
