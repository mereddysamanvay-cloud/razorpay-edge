"""Writes decision_intelligence_report.md. The methodology, equations, thresholds and decision tree are read from the live configuration through
api/intelligence.py, so the report cannot drift from the code. Run: py scripts/make_decision_intelligence_report.py [session_id]"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api import intelligence, store  # noqa: E402
from src.config import load_playbook_cfg, load_scoring  # noqa: E402

sid = sys.argv[1] if len(sys.argv) > 1 else "demo-p2"
s = store.load_session(sid)
d = intelligence.build(s)
sc, pb = load_scoring(), load_playbook_cfg()
w = d["worked"]
L = ["# Decision Intelligence: change report", "", f"Generated from scoring version **{sc['scoring_version']}** and the analysis **{s['name']}** ({s['version']}).", "",
     "## 1. Methodology actually implemented", "",
     "EDGE is a rule-based, weighted additive scoring system. There is no machine-learning model and no churn probability. Not used anywhere: " + ", ".join(x.lower() for x in d["not_used"]) + ".", ""]
L += ["### Weights and thresholds in force", "", "| Item | Value |", "|---|---|"]
L += [f"| Dimension weights (P / R / E / C) | {sc['weights']['performance']:g} / {sc['weights']['relationship']:g} / {sc['weights']['engagement']:g} / {sc['weights']['commercial']:g} (sum {d['weights_sum']:g}) |",
      f"| Strongest-dimension share | {1 - sc['aggregation']['weighted_share']:g} (weighted-mean share {sc['aggregation']['weighted_share']:g}) |",
      f"| Convergence bonus | {sc['aggregation']['convergence_bonus_per_extra_dim']} per extra dimension at {sc['aggregation']['convergence_threshold']}+, maximum {sc['aggregation']['convergence_cap']} |",
      f"| Risk bands | High ≥ {sc['bands']['high']}, Moderate ≥ {sc['bands']['medium']}, else Low |", f"| Driver minimum | {sc['driver_min_score']} |",
      f"| Net revenue rate / months | {d['assumptions']['net_revenue_rate']:g} / {d['assumptions']['saved_merchant_months']} |", f"| Outreach cost | Rs {d['assumptions']['false_alarm_cost_inr']:,.0f} |",
      f"| Capacity | {d['assumptions']['max_outreaches']} |", f"| Confidence factor (High / Medium / Low) | {' / '.join(str(v) for v in __import__('src.config', fromlist=['load_settings']).load_settings()['selection']['confidence_factor'].values())} |", ""]
L += ["### Equations", ""]
for e in d["equations"]:
    L += [f"**{e['title']}** ({e['kind']})", "", f"    {e['formula']}", "", e["plain"], ""]
L += ["### Features", "", "| Dimension | Feature | Source | Calculation | Limitation |", "|---|---|---|---|---|"]
for dim in d["features"]:
    for f in dim["features"]:
        L.append(f"| {dim['name']} | {f['feature']} | {f['source']} | {f['calc']} | {f['limit']} |")
if w["score"]:
    x = w["score"]
    L += ["", f"### Worked example: {x['merchant']['name']} ({x['merchant']['id']})", "", "| Dimension | S | w | S × w |", "|---|---:|---:|---:|"]
    L += [f"| {k} | {x['dims'][k]:.1f} | {x['weights'][k]:g} | {x['weighted_points'][k]:.2f} |" for k in x["dims"]]
    L += ["", f"Weighted mean {x['weighted_mean']:.2f}; strongest {x['strongest']:.2f}; bonus {x['bonus']}. Score = {x['share']:g} × {x['weighted_mean']:.2f} + {1 - x['share']:g} × {x['strongest']:.2f} + {x['bonus']} = **{x['total']}** ({x['band']})."]
if w["priority"]:
    a, b = w["priority"]["higher_priority"], w["priority"]["higher_risk"]
    L += ["", f"### Priority is not risk: {a['name']} ({a['segment']}, {a['band']}, score {a['score']}, index Rs {a['index']:,}, rank {a['rank']}) ranks above {b['name']} ({b['segment']}, {b['band']}, score {b['score']}, index Rs {b['index']:,}, rank {b['rank']})."]
L += ["", "## 2. Decision tree (the actual rules)", "", "| Step | Question | Condition and thresholds | Result |", "|---|---|---|---|"]
for n in d["tree"]:
    L.append(f"| {n['title']} | {n['question']} | {n['condition']} | {n.get('result') or n.get('yes_label') or ''} |")
L += ["", "Playbook selection is not a fixed top-to-bottom order: PB-1 to PB-4 are tested independently, the highest fit (the matching dimension's score) is primary, ties go in the order "
      + ", ".join(pb["tie_break_order"]) + f", and the runner-up is secondary only if its fit is at least {pb['secondary_min_fit']}.", ""]
L += ["## 3. Playbooks", "", "| ID | Name | Rule EDGE uses | Uses a slot |", "|---|---|---|---|"] + [f"| {p['id']} | {p['name']} | {p['rule']} | {'Yes' if p['uses_slot'] else 'No'} |" for p in d["playbooks"]]
(ROOT / "decision_intelligence_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote decision_intelligence_report.md")
