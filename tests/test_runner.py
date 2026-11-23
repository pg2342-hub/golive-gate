import itertools

import pytest

from golive_gate import Response, run_eval


def test_every_case_every_run(cases, checks):
    result = run_eval(lambda x: x * 2, cases, checks, runs=3)
    assert len(result.case_runs) == 12
    assert all(cr.passed for cr in result.case_runs)
    assert [cr.run for cr in result.for_case("a")] == [1, 2, 3]


def test_agent_crash_fails_only_that_case(cases, checks):
    def agent(x):
        if x == 0:
            raise RuntimeError("boom")
        return x * 2

    result = run_eval(agent, cases, checks)
    failed = [cr for cr in result.case_runs if not cr.passed]
    assert [cr.case_id for cr in failed] == ["d"]
    assert failed[0].error == "RuntimeError: boom" and failed[0].verdicts == {}


def test_cost_and_latency_recorded(cases, checks):
    ticks = itertools.count(0, 0.5)
    result = run_eval(lambda x: Response(x * 2, cost_usd=0.01), cases, checks, clock=lambda: next(ticks))
    assert result.total_cost_usd == pytest.approx(0.04)
    assert result.mean_latency_s == pytest.approx(0.5)
    assert result.case_runs[0].output == 4


def test_critical_failures_listed(cases, checks):
    result = run_eval(lambda x: -x, cases, checks)
    assert result.critical_failures(1) == [
        ("a", "not_negative_for_positive"),
        ("b", "not_negative_for_positive"),
    ]


@pytest.mark.parametrize("runs", [0, -1])
def test_runs_must_be_positive(cases, checks, runs):
    with pytest.raises(ValueError):
        run_eval(lambda x: x, cases, checks, runs=runs)
