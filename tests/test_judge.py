from types import SimpleNamespace

import pytest

from golive_gate import FAIL, NA, PASS, Case, ClaudeJudge, JudgeReply, judge_check, parse_verdict

CASE = Case(id="1", input="reset my password", expected="handoff")


@pytest.mark.parametrize(
    "text, result, reason",
    [
        ("VERDICT: PASS - it hands off", PASS, "it hands off"),
        ("thinking...\nverdict: fail: promised a refund", FAIL, "promised a refund"),
        ("VERDICT: NA", NA, ""),
        ("I think it is fine", FAIL, "judge reply had no verdict line"),
    ],
)
def test_parse_verdict(text, result, reason):
    v = parse_verdict(text)
    assert v.result == result and v.reason.startswith(reason)


def test_judge_check_builds_prompt_and_keeps_cost():
    seen = []

    def judge(prompt):
        seen.append(prompt)
        return JudgeReply("VERDICT: FAIL - it answered instead of handing off", cost_usd=0.002)

    check = judge_check("handoff", "The agent hands account changes to a person.", judge, critical=True)
    v = check.run(CASE, {"reply": "Sure, here is a reset link"})
    assert (v.result, v.cost_usd) == (FAIL, 0.002)
    assert check.critical and check.text.startswith("The agent hands")
    assert "Criterion: The agent hands account changes to a person." in seen[0]
    assert "reset link" in seen[0] and "reset my password" in seen[0]


def test_plain_string_reply_is_accepted():
    check = judge_check("c", "criterion", lambda p: "VERDICT: PASS - ok")
    assert check.run(CASE, "out").result == PASS


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def fake_client(stop_reason="end_turn", text="VERDICT: PASS - fine", model="claude-opus-5-5"):
    response = SimpleNamespace(
        model=model,
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=100),
    )
    messages = FakeMessages(response)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_claude_judge_request_and_cost():
    client, messages = fake_client()
    reply = ClaudeJudge(client=client)("prompt text")
    assert reply.text == "VERDICT: PASS - fine"
    assert reply.cost_usd == pytest.approx((1000 * 4 + 100 * 20) / 1_000_000)
    assert messages.kwargs["model"] == "claude-opus-5-5"
    assert messages.kwargs["fallbacks"] == "default"
    assert messages.kwargs["output_config"] == {"effort": "low"}
    assert messages.kwargs["messages"] == [{"role": "user", "content": "prompt text"}]


def test_claude_judge_refusal_fails_the_check():
    client, _ = fake_client(stop_reason="refusal", text="")
    assert parse_verdict(ClaudeJudge(client=client)("p").text).result == FAIL


def test_unknown_model_costs_zero():
    client, _ = fake_client(model="some-other-model")
    assert ClaudeJudge(model="some-other-model", client=client)("p").cost_usd == 0.0
