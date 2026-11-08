# Merchant Retention Intelligence Agent (Razorpay Campus AI Build-a-thon, Problem 2)

Ranks 100 synthetic merchants by churn **risk** (heuristic, not a probability), explains why, picks one of the six supplied playbooks, selects at most 15 for outreach, and drafts CSM-reviewed messages. Numbers/decisions are deterministic; Claude is an optional, bounded layer for interpretation and wording.

> No churn labels exist, so no accuracy/precision/recall is claimed. See `outputs/validation_report.md`.

## Setup (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
Put your **own** Anthropic key in `.env` (git-ignored; never paste it in chat or commit it):
```
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-5-5
```

## Run
```powershell
python -m src.pipeline                              # deterministic mode, no key, no cost
python -m src.pipeline --llm --confirm-paid-calls   # adds Claude reasoning + drafts (~115 paid calls)
python -m pytest -q                                 # 61 tests
```

## Where things are
| Path | Purpose |
|---|---|
| `outputs/top_15_outreach.csv` | the 15 selected merchants, reasons, playbooks, drafts |
| `outputs/merchant_risk_assessments.{json,csv}` | all 100 merchants, full evidence |
| `outputs/portfolio_insights.md` | management view, revenue exposure, sensitivity |
| `outputs/validation_report.md` | tests, limitations (not predictive accuracy) |
| `outputs/sensitivity_analysis.csv` | rankings under 12 configurations |
| `docs/` | source audit, methodology, agent architecture, original build brief |
| `config/` | all weights, thresholds, assumptions (hypotheses are labelled) |
| `knowledge/`, `prompts/` | agent knowledge base and prompts |
| `src/`, `tests/` | code |

## Decisions that need your confirmation
1. Value-weighted vs risk-first selection (`selection.rank_by` in `config/settings.yaml`): moves 6 of 15 picks.
2. Whether PB-5 (growth check-in) should consume the 15-outreach capacity (default: no).
3. Seasonal industry mapping: Gifting & Festive, Education / Coaching, Travel & Hospitality.
4. Channel/consent rules (none supplied; drafts are channel-neutral).

## Razorpay EDGE web app (Merchant Relationship Intelligence)
```powershell
.\run.ps1          # builds the UI on first run, then serves app + API at http://localhost:8000
```
Dev mode: `python -m uvicorn api.main:app --port 8000` plus `cd web; npm run dev` (http://localhost:5173).
- Backend `api/` (FastAPI) wraps the engine in `src/`; frontend `web/` (React, TypeScript, Tailwind, Recharts).
- Logo: put the supplied file at `web/public/razorpay-edge-logo.png` (then rebuild: `cd web; npm run build`). It is never redrawn in code.
- Claude: `ANTHROPIC_API_KEY` in `.env`, read server-side only. The key is never sent to the browser. Paid analysis requires an explicit confirmation in the UI.
- Persistence: `data/sessions/` (analyses, statuses, drafts, scenarios), `data/uploads/` (staged workbooks).
