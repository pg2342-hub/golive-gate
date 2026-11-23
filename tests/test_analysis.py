import pytest

from golive_gate import CheckSet, Gate, ablate, diff, run_eval
from golive_gate.analysis import ablation_markdown, diff_markdown
from golive_gate.gates import evaluate
from golive_gate.report import to_dict

GATE = Gate.from_dict({"rules": [{"min_pass": "all"}]})


def test_without_checks_regrades_without_calling_agent(cases, checks):
    calls = []
    result = run_eval(lambda x: calls.append(x) or -x, cases, checks)
    reduced = result.without_checks("not_negative_for_positive")
    assert len(calls) == 4
    assert [c.id for c in reduced.checks] == ["doubles"]
    assert all("not_negative_for_positive" not in cr.verdicts for cr in reduced.case_runs)


def test_ablation_finds_the_load_bearing_check(cases):
    cs = CheckSet()
    cs.check("doubles")(lambda case, out: out == case.expected)
    cs.check("sign", critical=True)(lambda case, out: "na" if case.input <= 0 else out > 0)
    cs.check("is_int")(lambda case, out: isinstance(out, int))

    # Wrong only on case a, in a way that only "doubles" notices.
    result = run_eval(lambda x: 5 if x == 2 else x * 2, cases, cs)
    baseline, rows = ablate(GATE, result)
    by_id = {r.check: r for r in rows}
    assert baseline == "no-go"
    assert by_id["doubles"].cases_caught == ["a"] and by_id["doubles"].decision == "go"
    assert by_id["sign"].cases_caught == [] and by_id["sign"].decision == "no-go"
    assert "| doubles |  | GO | a |" in ablation_markdown(baseline, rows)


def _results(agent, cases, checks):
    result = run_eval(agent, cases, checks)
    return to_dict(result, GATE, evaluate(GATE, result))


def test_diff_regressions_and_fixes(cases, checks):
    good = _results(lambda x: x * 2, cases, checks)
    bad = _results(lambda x: 7 if x in (2, 3) else x * 2, cases, checks)
    d = diff(good, bad)
    assert (d.before, d.after, d.regressed, d.fixed) == ("go", "no-go", ["a", "b"], [])
    assert d.has_regressions
    back = diff(bad, good)
    assert back.fixed == ["a", "b"] and not back.has_regressions
    assert "Regressed (passes on fewer runs than before): a, b" in diff_markdown(d)


def test_diff_added_and_removed(cases, checks):
    a = _results(lambda x: x * 2, cases, checks)
    b = _results(lambda x: x * 2, cases[:3], checks)
    d = diff(a, b)
    assert d.removed == ["d"] and diff(b, a).added == ["d"]


def test_diff_catches_flaky_regression(cases, checks):
    calls = {"n": 0}

    def flaky(x):  # case a fails on run 2 only
        calls["n"] += 1
        return 7 if x == 2 and calls["n"] > 4 else x * 2

    good = run_eval(lambda x: x * 2, cases, checks, runs=2)
    bad = run_eval(flaky, cases, checks, runs=2)
    d = diff(to_dict(good, GATE, evaluate(GATE, good)), to_dict(bad, GATE, evaluate(GATE, bad)))
    assert d.regressed == ["a"] and d.has_regressions


def test_removing_a_passing_case_counts_as_regression(cases, checks):
    lenient = Gate.from_dict({"rules": [{"min_pass": 1}]})
    full = run_eval(lambda x: x * 2, cases, checks)
    fewer = run_eval(lambda x: x * 2, cases[:3], checks)
    d = diff(to_dict(full, lenient, evaluate(lenient, full)), to_dict(fewer, lenient, evaluate(lenient, fewer)))
    assert d.removed == ["d"] and d.removed_passing == ["d"] and d.has_regressions
    assert d.before == d.after == "go"


def test_diff_rejects_files_that_are_not_results():
    with pytest.raises(ValueError, match="not a golive results.json"):
        diff({"decision": "go"}, {"cases": []})
