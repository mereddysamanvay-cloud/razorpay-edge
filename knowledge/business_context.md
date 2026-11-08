# Business context (Problem 2: Merchant churn early-warning)

- Razorpay merchants are businesses that accept online payments. All data is **synthetic**; snapshot date **30 Sep 2026**.
- Customer Success Managers (CSMs) often learn a merchant is leaving only after volume has moved to a competitor.
- **Churn** (source definition): the merchant moves *most of its payment volume away* within the **next 90 days**.
  A fall in TPV is a risk *signal*, not proof of churn. Account closure or inactivity are NOT the definition.
- The CSM team can run **at most 15 proactive outreaches** this month. Wrong picks waste scarce time.
- Actual churn labels are hidden. The agent produces a heuristic **risk score**, never a churn probability.
- Decoys that look risky but usually are not: **seasonal** merchants (Gifting & Festive, Education / Coaching, Travel & Hospitality),
  **naturally low-volume** merchants, and **busy-but-healthy** merchants (many tickets because they are growing and tickets get resolved).
- Seasonality never exempts a merchant from other, independent risk signals.

## Units
- TPV is in **Rs lakh per month** (1 lakh = 100,000). M6 is the most recent month.
- Net revenue is about **1% of TPV**. Value of a saved merchant = 12 months of net revenue at M6 TPV.
- Cost of a false alarm = Rs 1,500 (1.5 CSM hours).
