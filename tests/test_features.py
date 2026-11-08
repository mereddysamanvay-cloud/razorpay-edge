import math

import pytest

from src.analytics.feature_engineering import coefficient_of_variation, consecutive_declines, pct_change, slope_pct_per_month
from tests.helpers import run_one


def test_hand_calculated_c2001(built):
    _, _, df = built
    r = df.set_index("merchant_id").loc["C2001"]
    # early avg (8.7+9.2+8.1)/3 = 8.6667 ; recent avg (7.5+6.2+5.8)/3 = 6.5 -> -25.0%
    assert r["recent_vs_early_pct"] == pytest.approx(-25.0, abs=0.05)
    assert r["consecutive_declines"] == 4
    assert r["success_drop_pp"] == pytest.approx(86.8 - 96.1)  # percentage points, not percent
    assert r["annual_value_at_stake_inr"] == pytest.approx(5.8 * 100000 * 0.01 * 12)  # Rs 69,600


def test_zero_and_missing_denominators():
    assert math.isnan(pct_change(5.0, 0.0))
    assert math.isnan(pct_change(5.0, float("nan")))
    assert pct_change(5.0, 10.0) == -50.0


def test_constant_series():
    assert consecutive_declines([5, 5, 5, 5, 5, 5]) == 0
    assert slope_pct_per_month([5, 5, 5, 5, 5, 5]) == pytest.approx(0.0)
    assert coefficient_of_variation([5, 5, 5, 5, 5, 5]) == pytest.approx(0.0)


def test_consecutive_declines_stops_at_recovery():
    assert consecutive_declines([10, 9, 8, 7, 8, 9]) == 0
    assert consecutive_declines([10, 11, 9, 8, 7, 6]) == 4


def test_missing_csat_not_scored_as_poor():
    r = run_one(last_csat_1_to_5=float("nan"))
    assert r["csat_missing"] and not r["csat_low"]
    assert r["dim_relationship"] == 0
    assert "last_csat_1_to_5" in r["missing_fields"]


def test_missing_note_flagged_and_not_penalised():
    r = run_one(account_manager_note=None)
    assert r["note_missing"] and r["risk_band"] == "low"


def test_seasonal_flag_does_not_erase_other_signals():
    r = run_one(industry="Education / Coaching", tpv=[13, 13, 13, 9, 8.5, 10.5], unresolved_tickets=5.0,
                support_tickets_last_90d=6.0, last_csat_1_to_5=1.0)
    assert r["seasonal_adjustment_applied"]
    assert r["risk_band"] in ("medium", "high")  # service risk is not discounted by seasonality
    assert r["dim_relationship"] >= 70


def test_peer_context_columns(built):
    _, feats, _ = built
    assert {"tpv_change_vs_segment_median_pp", "industry_peer_count"} <= set(feats.columns)
