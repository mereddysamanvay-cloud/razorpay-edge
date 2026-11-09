"""Weight scenarios and ranking-robustness testing.

Re-runs the real engine (scoring -> playbook selection -> prioritisation) with alternative dimension weights and feature-level
parameters. This measures how stable the ranking is to the design hypotheses. It is not prediction accuracy: no churn labels exist.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.prioritisation import prioritise
from src.analytics.risk_scoring import score_merchants
from src.config import clone, load_playbook_cfg, load_scoring, load_settings
from src.crm.playbook_selector import apply_selection

DIMS = ("performance", "relationship", "engagement", "commercial")
DIM_LABEL = {"performance": "Performance", "relationship": "Relationship", "engagement": "Engagement", "commercial": "Commercial"}
PRESETS = {  # percent; test scenarios, not recommended final weights
    "Baseline": (35, 25, 15, 25), "Equal": (25, 25, 25, 25), "Performance-led": (45, 20, 15, 20),
    "Relationship-led": (25, 40, 15, 20), "Commercial-led": (25, 20, 15, 40),
}
SEED = 20261108
WEIGHT_BOUNDS = (10, 50)  # each dimension, percent
PARAM_BOUNDS = {  # feature-level parameters tested around the baseline value
    "aggregation.weighted_share": (0.7, 0.9),
    "tpv.zero_at_pct": (-10.0, 0.0), "tpv.full_at_pct": (-50.0, -30.0),
    "success.zero_at_pp": (-2.0, 0.0), "success.full_at_pp": (-12.0, -8.0),
    "performance.max_share": (0.6, 0.9), "engagement.login_share": (0.4, 0.8),
}
ROBUST_AT, LOW_AT = 0.9, 0.1


def preset_weights(name: str) -> dict:
    return dict(zip(DIMS, PRESETS[name]))


def validate_weights(w: dict) -> dict:
    """Percent in, fractions out. Raises ValueError with a message fit to show the user."""
    if set(w) != set(DIMS):
        raise ValueError("Provide weights for performance, relationship, engagement and commercial.")
    vals = {d: float(w[d]) for d in DIMS}
    if any(v < 0 for v in vals.values()):
        raise ValueError("Weights cannot be negative.")
    total = sum(vals.values())
    if abs(total - 100.0) > 0.01:
        raise ValueError(f"Weights must add up to 100%. They currently add up to {total:g}%.")
    return {d: v / 100.0 for d, v in vals.items()}


def apply_overrides(scoring: dict, ov: dict | None) -> dict:
    cfg = clone(scoring)
    if not ov:
        return cfg
    if ov.get("weights"):
        cfg["weights"] = validate_weights(ov["weights"])
    for path, val in (ov.get("params") or {}).items():
        a, b = path.split(".")
        cfg[a][b] = val
    return cfg


def is_baseline(ov: dict | None, scoring: dict | None = None) -> bool:
    if not ov:
        return True
    base = {d: round(v * 100, 4) for d, v in (scoring or load_scoring())["weights"].items()}
    w = ov.get("weights")
    same_w = not w or all(abs(float(w[d]) - base[d]) < 1e-6 for d in DIMS)
    return same_w and not ov.get("params")


def engine_settings(assumptions: dict, capacity: int) -> dict:
    s = clone(load_settings())
    s["source_assumptions"].update({k: v for k, v in assumptions.items() if k in s["source_assumptions"]})
    s["source_assumptions"]["max_outreaches"] = int(capacity)
    return s


def evaluate(feats: pd.DataFrame, scoring: dict, settings: dict, playbooks: pd.DataFrame) -> pd.DataFrame:
    return prioritise(apply_selection(score_merchants(feats, scoring), load_playbook_cfg(), playbooks), settings)


def playbook_frame(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(records)[["playbook_id", "name", "what_happens", "when_it_applies"]].astype(str)


def current_weights(scoring: dict) -> dict:
    return {d: round(scoring["weights"][d] * 100, 4) for d in DIMS}


# ------------------------------------------------------------------ explanations
def why_moved(mid: str, base: pd.DataFrame, new: pd.DataFrame, bw: dict, nw: dict) -> str:
    b, n = base.loc[mid], new.loc[mid]
    delta = float(n["risk_score"] - b["risk_score"])
    pts = {d: float(n[f"dim_{d}"]) * nw[d] - float(b[f"dim_{d}"]) * bw[d] for d in DIMS}
    top = max(DIMS, key=lambda d: abs(pts[d]))
    parts = []
    if abs(delta) >= 0.05:
        parts.append(f"risk score {b['risk_score']:.1f} to {n['risk_score']:.1f} ({delta:+.1f})")
    if b["risk_band"] != n["risk_band"]:
        parts.append(f"category {b['risk_band']} to {n['risk_band']}")
    if abs(pts[top]) >= 0.05:
        parts.append(f"largest effect: {DIM_LABEL[top].lower()} weight {bw[top]:g}% to {nw[top]:g}% on a {DIM_LABEL[top].lower()} score of {float(n[f'dim_{top}']):.0f}")
    return "; ".join(parts) if parts else "score unchanged; position changes only because other merchants moved"


def summarise(df: pd.DataFrame, selected: list[str]) -> dict:
    by = df.set_index("merchant_id")
    sub = by.loc[selected] if selected else by.iloc[0:0]
    return {"bands": {k: int((df["risk_band"] == k).sum()) for k in ("high", "medium", "low")},
            "run_rate_inr": float(sub["annual_value_at_stake_inr"].sum()) if len(sub) else 0.0,
            "drivers": {str(k): int(v) for k, v in sub["primary_dimension"].fillna("none").value_counts().items()},
            "segments": {str(k): int(v) for k, v in sub["segment"].value_counts().items()},
            "seasonal_selected": int(sub["is_seasonal_industry"].sum()) if len(sub) else 0,
            "incomplete_selected": int((sub["completeness_score"] < 100).sum()) if len(sub) else 0}


# ------------------------------------------------------------------ robustness
def grid(n: int, seed: int = SEED) -> list[dict]:
    """Deterministic: same n and seed always return the same configurations. Weights stay within WEIGHT_BOUNDS and sum to 100."""
    rng = np.random.default_rng(seed)
    out: list[dict] = []
    lo, hi = WEIGHT_BOUNDS
    while len(out) < n:
        w = rng.dirichlet([4, 4, 4, 4]) * 100
        if w.min() < lo or w.max() > hi:
            continue
        w = np.round(w, 1)
        w[0] = round(100 - w[1:].sum(), 1)
        if w.min() < lo or w.max() > hi:
            continue
        params = {k: round(float(rng.uniform(*b)), 3) for k, b in PARAM_BOUNDS.items()}
        out.append({"weights": dict(zip(DIMS, map(float, w))), "params": params})
    return out


def _rank_map(df: pd.DataFrame) -> dict:
    return {m: (int(r) if pd.notna(r) else None) for m, r in zip(df["merchant_id"], df["outreach_priority_rank"])}


def stability(feats: pd.DataFrame, scoring: dict, assumptions: dict, playbooks: pd.DataFrame, capacity: int, n: int = 300, seed: int = SEED, progress=None) -> dict:
    settings = engine_settings(assumptions, capacity)
    ids = list(feats["merchant_id"])
    runs: list[tuple[str, dict, pd.DataFrame]] = []
    presets = [(name, {"weights": preset_weights(name)}) for name in PRESETS]
    cfgs = [(f"Configuration {i + 1}", c) for i, c in enumerate(grid(n, seed))]
    total = len(presets) + len(cfgs)
    for i, (name, ov) in enumerate(presets + cfgs):
        runs.append((name, ov, evaluate(feats, apply_overrides(scoring, ov), settings, playbooks)))
        if progress and i % 10 == 0:
            progress(i / total)
    base_name, _, base = runs[0]
    base_sel = list(base.loc[base["selected_for_outreach"], "merchant_id"])
    base_rank = _rank_map(base)
    by_id = base.set_index("merchant_id")

    scen_rows, tops = [], {}
    preset_rank = {name: _rank_map(d) for name, _, d in runs[: len(presets)]}
    for name, ov, d in runs[: len(presets)]:
        sel = list(d.loc[d["selected_for_outreach"], "merchant_id"])
        tops[name] = set(sel)
        sm = summarise(d, sel)
        moves = [(m, abs(base_rank[m] - preset_rank[name][m])) for m in base_rank if base_rank[m] is not None and preset_rank[name].get(m) is not None]
        movers = [{"merchant_id": m, "from": base_rank[m], "to": preset_rank[name][m]} for m, x in sorted(moves, key=lambda z: (-z[1], z[0]))[:5] if x > 0]
        scen_rows.append({"scenario": name, "weights": ov["weights"], "high": sm["bands"]["high"], "medium": sm["bands"]["medium"], "low": sm["bands"]["low"],
                          "top_n": sorted(sel), "overlap_with_baseline": len(set(sel) & set(base_sel)), "moved_in": sorted(set(sel) - set(base_sel)),
                          "moved_out": sorted(set(base_sel) - set(sel)), "run_rate_inr": sm["run_rate_inr"], "drivers": sm["drivers"], "segments": sm["segments"],
                          "seasonal_selected": sm["seasonal_selected"], "incomplete_selected": sm["incomplete_selected"],
                          "avg_rank_movement": round(sum(x for _, x in moves) / len(moves), 2) if moves else 0.0, "max_rank_movement": max((x for _, x in moves), default=0), "top_movers": movers})
    overlap = {a: {b: len(tops[a] & tops[b]) for b in tops} for a in tops}

    sel_count = {m: 0 for m in ids}
    ranks = {m: [] for m in ids}
    scores = {m: [] for m in ids}
    bands = {m: set() for m in ids}
    for _, _, d in runs:
        for r in d.itertuples():
            m = r.merchant_id
            scores[m].append(float(r.risk_score))
            bands[m].add(r.risk_band)
            if pd.notna(r.outreach_priority_rank):
                ranks[m].append(int(r.outreach_priority_rank))
            if bool(r.selected_for_outreach):
                sel_count[m] += 1
    k = len(runs)
    preset_rank = {name: _rank_map(d) for name, _, d in runs[: len(presets)]}
    rows = []
    for m in ids:
        freq = sel_count[m] / k
        cls = "Robust priority" if freq >= ROBUST_AT else "Low priority" if (freq <= LOW_AT and m not in base_sel) else "Weight-sensitive"
        movers = []
        for name in list(PRESETS)[1:]:
            a, b = base_rank.get(m), preset_rank[name].get(m)
            flip = (m in base_sel) != (m in tops[name])
            if flip or (a is not None and b is not None and abs(a - b) >= 5):
                movers.append(f"{name} ({a or '-'} to {b or '-'})")
        rk = ranks[m]
        rows.append({"merchant_id": m, "name": by_id.loc[m, "business_name"], "segment": by_id.loc[m, "segment"], "baseline_selected": m in base_sel,
                     "baseline_rank": base_rank.get(m), "configurations": k, "times_selected": sel_count[m], "selection_frequency": round(freq, 3),
                     "avg_rank": round(float(np.mean(rk)), 1) if rk else None, "best_rank": min(rk) if rk else None, "worst_rank": max(rk) if rk else None,
                     "times_eligible": len(rk), "score_min": round(min(scores[m]), 1), "score_max": round(max(scores[m]), 1),
                     "bands_seen": sorted(bands[m]), "classification": cls, "moved_by": movers})
    rows.sort(key=lambda r: (-r["selection_frequency"], r["merchant_id"]))
    counts = {c: sum(1 for r in rows if r["classification"] == c) for c in ("Robust priority", "Weight-sensitive", "Low priority")}
    return {"seed": seed, "grid_size": n, "configurations": k, "capacity": capacity, "weight_bounds_pct": list(WEIGHT_BOUNDS),
            "param_bounds": {a: list(b) for a, b in PARAM_BOUNDS.items()}, "robust_at": ROBUST_AT, "low_at": LOW_AT,
            "baseline_top": sorted(base_sel), "scenarios": scen_rows, "overlap_matrix": overlap, "merchants": rows, "counts": counts,
            "note": "Measures how stable the ranking is to design hypotheses (weights and scales). It is not prediction accuracy; no churn labels exist."}
