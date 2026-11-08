# Limitations

1. **No churn labels.** The workbook records no outcome, so the risk score is a heuristic evidence index. No accuracy, precision, recall, AUC, calibrated probability or churn-likelihood percentage is claimed.
2. **Hypothesis weights.** Dimension weights, scales and thresholds are design hypotheses. The sensitivity test shows how stable the ranking is to them; it does not show they are right.
3. **Single six-month snapshot.** Payment success exists as two period averages only. Logins, products used, tickets and CSAT are current snapshots, so no adoption or service trend can be claimed.
4. **Unverified notes.** Account-manager notes are free text. Commercial signals depend on them entirely and need confirmation with the account manager.
5. **Missing data is unknown.** Missing CSAT or notes lower evidence completeness; they add no risk points.
6. **Exposure is not loss.** Annual run-rate is M6 TPV x net revenue rate x 12 months, an assumption-based proxy. It is not revenue lost, not expected savings and not a forecast.
7. **Value-weighted selection.** With limited capacity, small merchants can be High risk yet rarely shortlisted. This is a capacity decision, recorded in the Priority Queue.
8. **Small groups.** Industry groups hold roughly 5 to 12 merchants and some validation patterns match a handful, so conclusions about them are weak.
9. **Validation is design-conformance.** A pass means the engine behaves as the stated design intends. Expected interpretations are test expectations, not ground truth.
10. **Outcome capture is not a label.** Recorded outcomes are CSM observations and are not churn labels unless the actual churn definition is verified.
11. **Human review.** EDGE sends nothing. Every draft needs a named reviewer's approval, and contact is recorded manually.
