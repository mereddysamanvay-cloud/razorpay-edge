"""Contextual peer benchmarking: INFORMATIONAL only, never fed into the risk score.

Rationale: segments (3) are large enough for medians; industries (~10 merchants each) are thin, and
mixing small and enterprise merchants would mislead. With only six months of data we do not claim a
learned seasonal pattern. Peer deltas help a CSM see whether a decline is portfolio-wide or idiosyncratic.
"""
from __future__ import annotations

import pandas as pd


def add_peer_context(feats: pd.DataFrame) -> pd.DataFrame:
    out = feats.copy()
    seg_med = out.groupby("segment")["recent_vs_early_pct"].transform("median")
    out["segment_median_tpv_change_pct"] = seg_med
    out["tpv_change_vs_segment_median_pp"] = out["recent_vs_early_pct"] - seg_med
    ind_n = out.groupby("industry")["merchant_id"].transform("count")
    ind_med = out.groupby("industry")["recent_vs_early_pct"].transform("median")
    out["industry_peer_count"] = ind_n
    out["industry_median_tpv_change_pct"] = ind_med
    out["tpv_change_vs_industry_median_pp"] = out["recent_vs_early_pct"] - ind_med
    return out
