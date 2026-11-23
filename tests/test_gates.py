import pytest

from golive_gate import GO, NO_GO, PARTIAL, Gate, Rule, evaluate, run_eval


def gate(*rules, max_critical=0):
    return Gate.from_dict({"gate": {"rules": list(rules), "max_critical_failures": max_critical}})


def test_go_when_every_rule_holds(cases, checks):
    result = run_eval(lambda x: x * 2, cases, checks, runs=2)
    out = evaluate(gate({"min_pass": "all"}), result)
    assert out.decision == GO
    assert out.reasons == ["every rule held on all 2 run(s), no critical failures"]


def test_no_go_on_critical_failure_even_if_counts_hold(cases, checks):
    result = run_eval(lambda x: -x if x == 2 else x * 2, cases, checks)
    out = evaluate(gate({"min_pass": 3}), result)
    assert out.decision == NO_GO
    assert "critical failure" in out.reasons[0]


def test_critical_allowance(cases, checks):
    result = run_eval(lambda x: -x if x == 2 else x * 2, cases, checks)
    assert evaluate(gate({"min_pass": 3}, max_critical=1), result).decision == GO


def test_partial_rule_gives_partial(cases, checks):
    result = run_eval(lambda x: 99 if x == 0 else x * 2, cases, checks)
    out = evaluate(gate({"min_pass": 3}, {"group": "hard", "min_pass": "all", "on_fail": "partial"}), result)
    assert out.decision == PARTIAL
    assert out.reasons == ["run 1: group hard passed 1 of 2, needs 2 (partial)"]


def test_rule_must_hold_on_every_run(cases, checks):
    calls = {"n": 0}

    def flaky(x):  # case d fails only on the second run
        calls["n"] += 1
        return 99 if calls["n"] == 8 else x * 2

    result = run_eval(flaky, cases, checks, runs=3)
    out = evaluate(gate({"min_pass": "all"}), result)
    assert out.decision == NO_GO
    assert out.reasons == ["run 2: all cases passed 3 of 4, needs 4 (no-go)"]


def test_min_pass_rate_rounds_up():
    rule = Rule.from_dict({"min_pass_rate": 0.75})
    assert rule.required(4) == 3
    assert rule.required(5) == 4
    assert Rule.from_dict({"min_pass_rate": 0.7}).required(10) == 7


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"group": "x"}, "needs min_pass"),
        ({"min_pass_rate": 1.5}, "between 0 and 1"),
        ({"min_pass": 1, "on_fail": "maybe"}, "on_fail"),
    ],
)
def test_bad_rules(raw, message):
    with pytest.raises(ValueError, match=message):
        Rule.from_dict(raw)


def test_gate_needs_rules():
    with pytest.raises(ValueError):
        Gate.from_dict({"rules": []})


def test_unknown_group_is_an_error(cases, checks):
    result = run_eval(lambda x: x * 2, cases, checks)
    with pytest.raises(ValueError, match="no cases"):
        evaluate(gate({"group": "missing", "min_pass": 1}), result)


def test_rule_over_several_groups(cases, checks):
    result = run_eval(lambda x: 99 if x in (2, 0) else x * 2, cases, checks)
    rule = {"groups": ["easy", "hard"], "min_pass": 3}
    out = evaluate(gate(rule), result)
    assert out.decision == NO_GO
    assert out.reasons == ["run 1: group easy+hard passed 2 of 4, needs 3 (no-go)"]
    assert evaluate(gate({"group": ["easy", "hard"], "min_pass": 2}), result).decision == GO


def test_critical_allowance_is_a_total_across_runs(cases, checks):
    # The same critical failure on each of 3 runs is 3 failures, not 1 per run.
    result = run_eval(lambda x: -x if x == 2 else x * 2, cases, checks, runs=3)
    assert evaluate(gate({"min_pass": 3}, max_critical=2), result).decision == NO_GO
    assert evaluate(gate({"min_pass": 3}, max_critical=3), result).decision == GO


def test_agent_crash_counts_as_critical_failure(cases, checks):
    def crashy(x):
        if x == 2:
            raise RuntimeError("timeout")
        return x * 2

    result = run_eval(crashy, cases, checks)
    out = evaluate(gate({"min_pass": 3}), result)
    assert out.decision == NO_GO
    assert out.critical == {1: [("a", "agent_error")]}


def test_case_where_every_check_says_na_does_not_pass():
    from golive_gate import CheckSet, load_cases

    cs = CheckSet()
    cs.check("only_for_x")(lambda case, out: "na")
    result = run_eval(lambda x: x, load_cases([{"id": "a", "input": 1}]), cs)
    assert not result.case_runs[0].passed
    assert evaluate(gate({"min_pass": "all"}), result).decision == NO_GO


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"groups": [], "min_pass": 1}, "cannot be empty"),
        ({"min_pass": 1, "min_pass_rate": 0.5}, "not both"),
        ({"min_pass": 0.9}, "whole number"),
        ({"min_pass": -1}, "whole number"),
        ({"min_pass": 0}, "whole number"),
        ({"min_pass": True}, "whole number"),
        ({"min_pass": "most"}, "whole number"),
    ],
)
def test_rules_that_would_silently_pass_are_rejected(raw, message):
    with pytest.raises(ValueError, match=message):
        Rule.from_dict(raw)


@pytest.mark.parametrize("value", [-1, 0.5, "1", True])
def test_bad_critical_allowance_is_rejected(value):
    with pytest.raises(ValueError, match="max_critical_failures"):
        Gate.from_dict({"rules": [{"min_pass": 1}], "max_critical_failures": value})
