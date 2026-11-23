"""Run an agent over every case N times and grade each output with every check."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Callable

from .cases import Case
from .checks import FAIL, CheckSet, Verdict


@dataclass(frozen=True)
class Response:
    """What an agent may return when it wants cost recorded alongside its output."""

    output: Any
    cost_usd: float = 0.0


@dataclass
class CaseRun:
    case_id: str
    group: str
    run: int
    output: Any
    verdicts: dict[str, Verdict]
    latency_s: float
    cost_usd: float = 0.0  # what the agent cost
    error: str = ""

    @property
    def judge_cost_usd(self) -> float:
        return sum(v.cost_usd for v in self.verdicts.values())

    @property
    def passed(self) -> bool:
        return not self.error and all(v.result != FAIL for v in self.verdicts.values())

    @property
    def failed_checks(self) -> list[str]:
        return [cid for cid, v in self.verdicts.items() if v.result == FAIL]


@dataclass
class RunResult:
    cases: list[Case]
    checks: CheckSet
    runs: int
    case_runs: list[CaseRun] = field(default_factory=list)

    def for_run(self, run: int) -> list[CaseRun]:
        return [cr for cr in self.case_runs if cr.run == run]

    def for_case(self, case_id: str) -> list[CaseRun]:
        return [cr for cr in self.case_runs if cr.case_id == case_id]

    def critical_failures(self, run: int) -> list[tuple[str, str]]:
        critical = {c.id for c in self.checks if c.critical}
        return [(cr.case_id, cid) for cr in self.for_run(run) for cid in cr.failed_checks if cid in critical]

    @property
    def total_cost_usd(self) -> float:
        return sum(cr.cost_usd for cr in self.case_runs)

    @property
    def total_judge_cost_usd(self) -> float:
        return sum(cr.judge_cost_usd for cr in self.case_runs)

    def without_checks(self, *ids: str) -> RunResult:
        """The same outputs graded as if these checks did not exist (no agent or judge calls)."""
        kept = self.checks.without(*ids)
        clone = RunResult(cases=self.cases, checks=kept, runs=self.runs)
        for cr in self.case_runs:
            verdicts = {k: v for k, v in cr.verdicts.items() if k not in ids}
            clone.case_runs.append(
                CaseRun(cr.case_id, cr.group, cr.run, cr.output, verdicts, cr.latency_s, cr.cost_usd, cr.error)
            )
        return clone

    @property
    def mean_latency_s(self) -> float:
        return sum(cr.latency_s for cr in self.case_runs) / max(len(self.case_runs), 1)


Agent = Callable[[Any], Any]


def run_eval(
    agent: Agent,
    cases: Sequence[Case],
    checks: CheckSet,
    runs: int = 1,
    clock: Callable[[], float] = time.perf_counter,
) -> RunResult:
    """Call ``agent(case.input)`` for every case, ``runs`` times, and grade each output."""
    if runs < 1:
        raise ValueError("runs must be at least 1")
    if not len(checks):
        raise ValueError("no checks to grade with")
    result = RunResult(cases=list(cases), checks=checks, runs=runs)
    for run in range(1, runs + 1):
        for case in cases:
            start = clock()
            error, output, cost = "", None, 0.0
            try:
                raw = agent(case.input)
                if isinstance(raw, Response):
                    output, cost = raw.output, raw.cost_usd
                else:
                    output = raw
            except Exception as exc:  # an agent crash fails the case, it does not stop the run
                error = f"{type(exc).__name__}: {exc}"
            latency = clock() - start
            verdicts = {} if error else {c.id: c.run(case, output) for c in checks}
            result.case_runs.append(CaseRun(case.id, case.group, run, output, verdicts, latency, cost, error))
    return result
