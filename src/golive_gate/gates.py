"""Go-live gates written as data: go, partial or no-go, with the reason.

Every rule must hold on every run. The decision is:
  no-go    a critical check failed more often than allowed, or a rule with on_fail "no-go" broke
  partial  only rules with on_fail "partial" broke
  go       every rule held on every run
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .runner import RunResult

GO, PARTIAL, NO_GO = "go", "partial", "no-go"


@dataclass(frozen=True)
class Rule:
    name: str
    group: str | None = None  # None means every case
    min_pass: int | None = None  # an int, or None when min_pass_rate is used
    min_pass_rate: float | None = None
    all_must_pass: bool = False
    on_fail: str = NO_GO

    @classmethod
    def from_dict(cls, raw: dict) -> Rule:
        group = raw.get("group")
        name = raw.get("name") or (f"group {group}" if group else "all cases")
        min_pass = raw.get("min_pass")
        all_must = min_pass == "all"
        rate = raw.get("min_pass_rate")
        if not all_must and min_pass is None and rate is None:
            raise ValueError(f"rule {name!r} needs min_pass or min_pass_rate")
        if rate is not None and not 0 <= float(rate) <= 1:
            raise ValueError(f"rule {name!r}: min_pass_rate must be between 0 and 1")
        on_fail = raw.get("on_fail", NO_GO)
        if on_fail not in (NO_GO, PARTIAL):
            raise ValueError(f"rule {name!r}: on_fail must be 'no-go' or 'partial'")
        return cls(
            name=name,
            group=str(group) if group is not None else None,
            min_pass=None if all_must or min_pass is None else int(min_pass),
            min_pass_rate=None if rate is None else float(rate),
            all_must_pass=all_must,
            on_fail=on_fail,
        )

    def required(self, total: int) -> int:
        if self.all_must_pass:
            return total
        if self.min_pass is not None:
            return self.min_pass
        return math.ceil(round(self.min_pass_rate * total, 9))

    def describe(self, total: int) -> str:
        scope = f"group {self.group}" if self.group else "all cases"
        return f"{self.required(total)} of {total} in {scope}"


@dataclass(frozen=True)
class Gate:
    rules: tuple[Rule, ...]
    max_critical_failures: int = 0
    name: str = "go-live gate"

    @classmethod
    def from_dict(cls, raw: dict) -> Gate:
        raw = raw.get("gate", raw)
        rules = tuple(Rule.from_dict(r) for r in raw.get("rules", []))
        if not rules:
            raise ValueError("a gate needs at least one rule")
        return cls(
            rules=rules,
            max_critical_failures=int(raw.get("max_critical_failures", 0)),
            name=str(raw.get("name", "go-live gate")),
        )

    @classmethod
    def load(cls, path: str | Path) -> Gate:
        return cls.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


@dataclass
class RuleOutcome:
    rule: Rule
    run: int
    passed: int
    total: int
    required: int

    @property
    def held(self) -> bool:
        return self.passed >= self.required


@dataclass
class GateResult:
    decision: str
    reasons: list[str]
    outcomes: list[RuleOutcome] = field(default_factory=list)
    critical: dict[int, list[tuple[str, str]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": self.reasons,
            "rules": [
                {
                    "name": o.rule.name,
                    "run": o.run,
                    "passed": o.passed,
                    "total": o.total,
                    "required": o.required,
                    "held": o.held,
                    "on_fail": o.rule.on_fail,
                }
                for o in self.outcomes
            ],
            "critical_failures": {
                str(run): [{"case": c, "check": k} for c, k in fails] for run, fails in self.critical.items()
            },
        }


def evaluate(gate: Gate, result: RunResult) -> GateResult:
    groups = {c.group for c in result.cases}
    for rule in gate.rules:
        if rule.group is not None and rule.group not in groups:
            raise ValueError(f"rule {rule.name!r} names group {rule.group!r}, which has no cases")

    outcomes: list[RuleOutcome] = []
    critical: dict[int, list[tuple[str, str]]] = {}
    for run in range(1, result.runs + 1):
        rows = result.for_run(run)
        for rule in gate.rules:
            scoped = [r for r in rows if rule.group is None or r.group == rule.group]
            outcomes.append(
                RuleOutcome(rule, run, sum(r.passed for r in scoped), len(scoped), rule.required(len(scoped)))
            )
        fails = result.critical_failures(run)
        if fails:
            critical[run] = fails

    # Collect each problem once, with the runs it happened on, so three identical runs read as one line.
    problems: dict[str, list[int]] = {}
    hard_break = False
    soft_break = False
    for run, fails in critical.items():
        if len(fails) > gate.max_critical_failures:
            hard_break = True
            listed = ", ".join(f"{check} on case {case}" for case, check in fails)
            problems.setdefault(f"{len(fails)} critical failure(s): {listed}", []).append(run)
    for o in outcomes:
        if not o.held:
            if o.rule.on_fail == NO_GO:
                hard_break = True
            else:
                soft_break = True
            text = f"{o.rule.name} passed {o.passed} of {o.total}, needs {o.required} ({o.rule.on_fail})"
            problems.setdefault(text, []).append(o.run)
    reasons = [f"{_runs_label(runs, result.runs)}: {text}" for text, runs in problems.items()]

    decision = NO_GO if hard_break else PARTIAL if soft_break else GO
    if decision == GO:
        reasons.append(f"every rule held on all {result.runs} run(s), no critical failures")
    return GateResult(decision, reasons, outcomes, critical)


def _runs_label(runs: list[int], total: int) -> str:
    if total == 1:
        return "run 1"
    if len(runs) == total:
        return f"all {total} runs"
    label = "run" if len(runs) == 1 else "runs"
    return f"{label} {', '.join(str(r) for r in runs)}"
