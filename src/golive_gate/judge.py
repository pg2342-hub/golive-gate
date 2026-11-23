"""LLM judge checks: one yes/no criterion per call, with the judge's reason and cost.

A judge is any callable ``judge(prompt) -> JudgeReply``. ``ClaudeJudge`` calls Claude
through the official Anthropic SDK (``pip install "golive-gate[claude]"``); tests and
offline runs can pass any other callable, such as a recorded-reply lookup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from .checks import FAIL, NA, PASS, Check, Verdict

PROMPT = """You are grading one output of an AI agent against one criterion.

Criterion: {criterion}

Case:
{case}

Agent output:
{output}

Decide whether the output meets the criterion.
- PASS: it clearly meets the criterion.
- FAIL: it does not meet the criterion, or you cannot tell from the output.
- NA: the criterion does not apply to this case (the behavior had no chance to occur).

Answer on one line in exactly this form, and nothing else:
VERDICT: PASS|FAIL|NA - one short sentence saying why"""

_LINE = re.compile(r"VERDICT:\s*(PASS|FAIL|NA)\b\s*[-:–]?\s*(.*)", re.IGNORECASE)


@dataclass(frozen=True)
class JudgeReply:
    text: str
    cost_usd: float = 0.0


def parse_verdict(text: str) -> Verdict:
    """Read 'VERDICT: PASS - reason'. Anything unreadable is a FAIL, never a silent pass."""
    for line in reversed(text.strip().splitlines()):
        m = _LINE.search(line)
        if m:
            return Verdict({"PASS": PASS, "FAIL": FAIL, "NA": NA}[m.group(1).upper()], m.group(2).strip())
    return Verdict(FAIL, f"judge reply had no verdict line: {text.strip()[:200]!r}")


def judge_check(
    id: str,
    criterion: str,
    judge: Callable[[str], JudgeReply | str],
    render_case: Callable[[Any], str] | None = None,
    render_output: Callable[[Any], str] | None = None,
    critical: bool = False,
) -> Check:
    """A Check that asks ``judge`` whether one output meets ``criterion``."""
    show_case = render_case or (lambda case: f"id {case.id}\ninput: {case.input!r}\nexpected: {case.expected!r}")
    show_output = render_output or repr

    def grade(case: Any, output: Any) -> Verdict:
        prompt = PROMPT.format(criterion=criterion, case=show_case(case), output=show_output(output))
        reply = judge(prompt)
        if isinstance(reply, str):
            reply = JudgeReply(reply)
        v = parse_verdict(reply.text)
        return Verdict(v.result, v.reason, reply.cost_usd)

    return Check(id=id, fn=grade, text=criterion, critical=critical)


# USD per million tokens (input, output), first-party API list prices.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class ClaudeJudge:
    """Judge with Claude. Reads credentials the way the Anthropic SDK does (ANTHROPIC_API_KEY, etc.).

    Server-side refusal fallback is on, so a declined grading request is re-run on a
    fallback model inside the same call; if the whole chain declines, the check fails.
    """

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "low", client: Any = None) -> None:
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise ImportError('ClaudeJudge needs the Anthropic SDK: pip install "golive-gate[claude]"') from exc
            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.effort = effort

    def __call__(self, prompt: str) -> JudgeReply:
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": self.effort},
            messages=[{"role": "user", "content": prompt}],
        )
        cost = self.cost(response)
        if response.stop_reason == "refusal":
            return JudgeReply("VERDICT: FAIL - the judge declined to grade this output", cost)
        text = "".join(b.text for b in response.content if b.type == "text")
        return JudgeReply(text, cost)

    def cost(self, response: Any) -> float:
        price = PRICES.get(getattr(response, "model", self.model)) or PRICES.get(self.model)
        if not price:
            return 0.0
        usage = response.usage
        return (usage.input_tokens * price[0] + usage.output_tokens * price[1]) / 1_000_000
