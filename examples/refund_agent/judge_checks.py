"""The rule checks plus one LLM judge check. Needs an Anthropic API key:

    pip install "golive-gate[claude]"
    export ANTHROPIC_API_KEY=...
    golive run golive.judge.yml

Rules catch what a rule can state exactly (amounts, limits, fraud flags). The judge
grades what a rule cannot: whether a decline is explained kindly and clearly.
"""

from checks import checks as rule_checks

from golive_gate import NA, CheckSet, ClaudeJudge, judge_check

_judge = None


def claude(prompt):
    global _judge
    if _judge is None:  # created on first use, so importing this file needs no key
        _judge = ClaudeJudge()
    return _judge(prompt)


checks = CheckSet(rule_checks)

_tone = judge_check(
    "decline_tone",
    "If the agent declines the refund, its reply is polite, says why in plain words, and does not blame "
    "the customer. If the agent does not decline, the criterion does not apply.",
    judge=claude,
    render_case=lambda case: f"Refund request: {case.input}",
    render_output=lambda out: f"Action: {out['action']}\nReply to customer: {out['reply']}",
)


@checks.check("decline_tone", text=_tone.text)
def decline_tone(case, out):
    if out["action"] != "decline":
        return NA  # skip the judge call when the criterion cannot apply
    return _tone.run(case, out)
