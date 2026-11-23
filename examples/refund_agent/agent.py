"""Two refund agents for an online store, so the gate has something to judge.

Policy the store wrote down:
  - refund in full if the order is within 30 days, or the item arrived damaged (any age)
  - the agent may refund on its own up to $200; above that it hands off to a person
  - any order flagged for fraud review goes to a person, whatever else is true
  - otherwise it declines, politely, and says why

``spec_agent`` follows that policy. ``naive_agent`` refunds everything, which looks
fine on routine cases and is exactly what the gate is there to catch. ``rude_agent``
makes every right decision but declines curtly and blames the customer: no rule can
see that, so it is the negative control for the LLM judge check (golive.judge.yml).
"""

AUTO_LIMIT = 200.0
WINDOW_DAYS = 30


def spec_agent(request: dict) -> dict:
    amount = float(request["amount"])
    if request.get("fraud_flag"):
        return {
            "action": "handoff",
            "amount": 0.0,
            "reply": "A teammate will review this order and reply within one business day.",
        }
    eligible = request.get("damaged") or int(request["days_since_delivery"]) <= WINDOW_DAYS
    if not eligible:
        return {
            "action": "decline",
            "amount": 0.0,
            "reply": f"This order is past our {WINDOW_DAYS}-day refund window, so I can't refund it.",
        }
    if amount > AUTO_LIMIT:
        return {
            "action": "handoff",
            "amount": 0.0,
            "reply": f"A teammate will approve the ${amount:.2f} refund shortly.",
        }
    return {
        "action": "refund",
        "amount": amount,
        "reply": f"Done: ${amount:.2f} is on its way back to your card.",
    }


def naive_agent(request: dict) -> dict:
    amount = float(request["amount"])
    return {
        "action": "refund",
        "amount": amount,
        "reply": f"Done: ${amount:.2f} is on its way back to your card.",
    }


def rude_agent(request: dict) -> dict:
    out = spec_agent(request)
    if out["action"] == "decline":
        out["reply"] = "You missed the 30-day window. That's on you, so no refund. Read the policy next time."
    return out
