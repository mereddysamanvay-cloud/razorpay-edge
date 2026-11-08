TASK: Draft ONE short outreach message (60-110 words) from a Razorpay CSM to the merchant, for human review. Channel-neutral.

Inputs in <merchant_data>: business name, segment, the approved playbook (id, name, exact approved action text), and `allowed_facts` (verified merchant facts you may cite, with exact values).

Rules:
- Follow ONLY the approved playbook action. Do not add steps, offers or commitments beyond its text.
- Cite at most two facts, and only from `allowed_facts`, with exact values. No other numbers except playbook-stated ones (e.g. "3 days", "48 hours").
- Do NOT mention: risk, churn, scores, rankings, competitors, pricing pressure, the account manager's notes, or that the merchant is being monitored.
- Do NOT promise refunds, fee waivers, discounts, price changes, settlement dates or fixes. Do not claim a root cause is known.
- Tone matches the issue (helpful, calm, respectful). Match delivery to segment (Enterprise: senior/AM-led; Small: light-touch).
- Greeting "Hi <business name> team," and sign-off "[CSM name], Razorpay".
Return the tool fields: `subject`, `body`, `facts_used` (list of the allowed_facts keys you cited).
